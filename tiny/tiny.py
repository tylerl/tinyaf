import cgi
import json
import mimetypes
import os
import re
import sys
import traceback
import wsgiref.headers
import wsgiref.simple_server
if sys.version_info[0]==2:  # py2
  import SocketServer as socketserver
  import httplib  # pylint: disable=E0401
else:  # py3
  import socketserver
  import http

#############################################################################
## TODO:
#   * Simplified Router class that just saves a dict per route in the list


class Router(object):
  def __init__(self):
    self.errorhandlers = {}
    self.routes = []

  def route(self, path, handler=None, methods=None):
    def decorator(fn):
      r = re.compile(path if path.startswith("^") else self._escape("/" + path))
      self.routes.append((r, fn, methods or []))
      return fn
    if handler:
      return decorator(handler)
    return decorator

  def errorhandler(self, code, handler=None):
    def decorator(fn):
      self.errorhandlers[code] = fn
      return fn
    if handler:
      return decorator(handler)
    return decorator

  @staticmethod
  def _escape(val):
    """Encode non-regex patterns as regex."""
    esc = lambda s: re.escape(re.sub("//+", "/", s))
    def it(val):
      i=0
      yield "^"
      for m in re.finditer(r'({([a-zA-Z0-9\.]+)(?::((?:\\.|[^}])*))?})|(\*)', val):
        if m.start() > i: yield esc(val[i:m.start()])
        if m.group() == "*": yield r"[^/]+"
        else: yield "(?P<%s>%s)" % (m.groups()[1], m.groups()[2] or r'[^/]+')
        i = m.end()
      if i < len(val): yield esc(val[i:])
      yield "$"
    return "".join(it(val))


class Request(object):
  def __init__(self, environ, url_args=None):
    self.url_args = url_args or {}  # updated when routing decision is calcuated
    self.environ = environ
    self.path = environ['PATH_INFO']
    self.method = environ['REQUEST_METHOD']
    self.fieldstorage = cgi.FieldStorage(environ=environ, fp=environ.get('wsgi.input', None))
    self.route_matched = None
    try:
      self.fields = {k: self.fieldstorage[k].value for k in self.fieldstorage}
    except TypeError:
      self.fields = {}
    hlist = [(k[5:].replace("_","-").title(), v) for k, v in environ.items() if k.startswith("HTTP_")]
    self.headers = wsgiref.headers.Headers(hlist)

  def forward(self, application, env_update=None, force_wsgi=False):
    environ = self.environ.copy()
    if env_update: environ.update(env_update)
    if hasattr(application,'process_request') and not force_wsgi:
      return application.process_request(Request(environ, self.url_args.copy()))
    self.__response = None  # place to stick the response object in callback, else we lose it.
    def start_response(statusline, headers):
      code, status = statusline.split(" ", 1)
      self.__response = Response(content=None, code=int(code), headers=headers, status=status)
    content = application(self.environ, start_response)
    if not self.__response: raise AssertionError("start_response not called.")
    self.__response.content = content
    return self.__response

  def __getitem__(self, key):
    try: return self.url_args[key]
    except KeyError: return self.fields[key]

  def __contains__(self, key):
    return key in self.url_args or key in self.fields


class Response(object):
  def __init__(self, content=None, code=200, headers=None, **kwargs):
    self.response_instance = self  # override to send another class as the response instance
    self._default_headers = {}
    self.content = content or []
    self.status = kwargs.get('status', None)
    self.code = code
    headers = headers or []
    self.headers = wsgiref.headers.Headers(list(getattr(headers, 'items', lambda: headers)()))

  def write(self, content):
    self.content.append(content)

  def _finalize_wsgi(self, environ, start_response):
    self.environ = environ
    self.start_response = start_response
    self.content = self.finalize() or self.content or []
    self.code = self.code or 500
    for h, v in self._default_headers.items(): self.headers.setdefault(h, str(v))
    self.start_response("%i %s" % (self.code, self.status or self.http_status()[0]), list(self.headers.items()))

  def finalize(self):
    pass

  def __iter__(self):
    return iter(self.content)

  def http_status(self):
    if sys.version_info[0]==2:
      return httplib.responses.get(self.code, 'Unknown')
    else:
      try:
        s = http.HTTPStatus(self.code); return s.phrase, s.description  # pylint: disable=E1120
      except ValueError: return "Unknown", ""


class StringResponse(Response):
  def __init__(self, content=None, charset='utf-8', content_type='text/html', **kwargs):
    content = [content] if content else []
    Response.__init__(self, content=content, **kwargs)
    self.content_type = content_type
    self.charset = charset

  def finalize(self):
    out = ''.join(self.content).encode(self.charset)
    self._default_headers['content-type'] = "%s; charset=%s" % (self.content_type, self.charset)
    self._default_headers['content-length'] = len(out)
    return (out,)


class JsonResponse(StringResponse):
  def __init__(self, val=None, sort_keys = True, **kwargs):
    self.val = val
    self.sort_keys = sort_keys
    self.json_args = kwargs.pop('json_args', {})
    kwargs.setdefault('content_type', 'application/json')
    StringResponse.__init__(self, **kwargs)

  def write(self, val):
    self.val = val

  def finalize(self):
    self.content = (json.dumps(self.val, sort_keys=self.sort_keys, **self.json_args),)
    return StringResponse.finalize(self)


class FileResponse(Response):
  def __init__(self, file, content_type=None, close=True, **kwargs):
    Response.__init__(self, **kwargs)
    self._close = close
    if not hasattr(file, 'read'):
      file = open(file, 'rb')
    if not content_type and hasattr(file, 'name'):
      content_type = mimetypes.guess_type(file.name)[0]
    if content_type:
      self._default_headers['content-type'] = content_type
    if hasattr(file, 'fileno'):
      self._default_headers['content-length'] = "%i" % (
          os.fstat(file.fileno()).st_size)
    self.file = file

  def finalize(self):
    if 'wsgi.file_wrapper' in self.environ:
      self.response_instance = self.environ['wsgi.file_wrapper'](self.file, 32768)

  def close(self):
    if self._close and hasattr(self.file, 'close'):
      self.file.close()

  def __iter__(self):
    return iter(lambda: self.file.read(32768), '')


class HttpError(Exception, StringResponse):
  """HttpError triggers your handle_STATUS handler if one is set."""

  def __init__(self, code=500, content="", **kwargs):
    Exception.__init__(self, "HTTP %i" % (code))
    StringResponse.__init__(self, content, code=code, **kwargs)


class App(Router):
  ResponseClass = StringResponse
  def __init__(self, router=None):
    self.router = router or Router()
    self.tracebacks_to_http = False
    self.tracebacks_to_stderr = True

  @property
  def routes(self):
    return self.router.routes

  @property
  def errorhandlers(self):
    return self.router.errorhandlers

  def request_handler(self, request, response):
    """Top-level request handler. Override to intercept every request."""
    url = request.path
    router = self.router
    fn, matched, url_args = self._lookup_route(url, request.method, router)
    request.url_args.update(url_args)
    request.route_matched = matched
    return fn(request, response)

  def _lookup_route(self, url, method, router=None):
    """Figure out which URL matches."""
    if not router:
      router = self.router
    methods_allowed = []
    for pattern, fn, methods in router.routes:
      match = re.match(pattern, url)
      if match:
        if methods and method not in methods:
          methods_allowed.extend(methods)
          continue
        return fn, match.group(0), match.groupdict()
    if methods_allowed:
      raise HttpError(405, headers={'Allow': ",".join(methods_allowed)})
    raise HttpError(404)

  def error_handler(self, request, http_error):
    """Top-level error handler. Override to incercept every error."""
    handler = self.router.errorhandlers.get(http_error.code,
                                            self._default_error_handler)
    return handler(request, http_error)

  def _default_error_handler(self, request, http_error):
    if http_error.content:  # Bail if content is already set
      return
    if self.tracebacks_to_http and hasattr(http_error, 'traceback'):
      http_error.headers['Content-type'] = 'text/plain'
      http_error.write("An error occurred:\n\n %s" % (http_error.traceback))
      return
    http_error.headers['Content-type'] = 'text/html'
    phrase, description = http_error.http_status()
    http_error.write("<h1>HTTP %s - %s</h1>" % (http_error.code, phrase))
    http_error.write("<p>%s.</p>\n" % (description or "Your request could not be processed"))
    if http_error.code == 405:
      http_error.write("<p><b>Methods allowed:</b> %s</p>\n" % (http_error.headers['Allow']))
      http_error.write("<p><b>Method used:</b> %s</p>\n" % (request.method))

  def __call__(self, environ, start_response):
    """WSGI entrypoint."""
    resp = self.process_request(Request(environ))
    resp._finalize_wsgi(environ, start_response)
    return resp.response_instance

  def process_request(self, request):
    """Call the base request handler and get a response."""
    return self._get_response_handled(self.request_handler, request, self.ResponseClass())

  def _get_response(self, fn, request, response):
    """Sort out the response/result ambiguity, and return the response."""
    result = fn(request, response)
    if result:
      if isinstance(result, Response):
        response = result
      else:
        response.write(result)
    return response

  def _get_response_handled(self, fn, request, response):
    """Try/catch on a response fetcher, call error handler."""
    try:
      return self._get_response(fn, request, response)
    except HttpError as e:
      return self._get_response_handled(self.error_handler, request, e)
    except Exception as e:
      http_error = HttpError(500)
      http_error.traceback = traceback.format_exc()
      http_error.exception = e
      if self.tracebacks_to_stderr: sys.stderr.write(http_error.traceback)
      return self._get_response(self.error_handler, request, http_error)

  def make_server(self, port=8080, host='', threaded=True):
    svr = wsgiref.simple_server.WSGIServer
    if threaded:  # Add threading mix-in
      svr = type('ThreadedServer', (socketserver.ThreadingMixIn, svr), {'daemon_threads': True})
    return wsgiref.simple_server.make_server(host, port, self, server_class=svr)

  def serve_forever(self, port=8080, host='', threaded=True):
    print("Serving on %s:%s -- ctrl+c to quit." % (host, port))
    try: self.make_server(port, host, threaded).serve_forever()
    except KeyboardInterrupt: pass
