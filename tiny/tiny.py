import cgi
import fnmatch
import functools
import json
import mimetypes
import os
import re
import sys
import traceback
import types
import wsgiref.headers
import wsgiref.simple_server
try:
  import socketserver  # py3
  import http
  def _http_status(code):
    try:
      s = http.HTTPStatus(code); return s.phrase, s.description  # pylint: disable=E1120
    except ValueError: return "Unknown", ""
except ImportError:
  import SocketServer as socketserver  # py2
  import httplib
  def _http_status(code):
    return httplib.responses.get(code, 'Unknown')

class Router(object):
  def __init__(self):
    self.errorhandlers = {}
    self.routes = []

  def route(self, path, *methods):
    """Decorator which gives you a handler for a given path."""

    def decorator(fn):
      r = re.compile(path if path.startswith("^") else self._escape("/" + path))
      self.routes.append((r, fn, methods))
      return fn
    return decorator

  def errorhandler(self, code):
    """Decorator which gives you a handler for a given HttpError status."""
    def decorator(fn):
      self.errorhandlers[code] = fn
      return fn
    return decorator

  def mount(self, path, router):
    if not path.startswith("^"):
      path = self._escape("/" + path + "/", partial=True)
    self.routes.append((path, router, []))

  @staticmethod
  def _escape(val, partial=False):
    """Encode non-regex patterns as regex."""
    esc = lambda s: re.escape(re.sub("//+", "/", s))
    def it(val):
      i=0
      yield "^"
      for m in re.finditer(r'({([a-zA-Z0-9\.]+)(?::((?:\\.|[^}])*))?})|(\*)', val):
        if m.start() > i: yield esc(val[i:m.start()])
        if m.group() == "*": yield r"[^/]+"
        else:
          yield "(?P<%s>%s)" % (m.groups()[1], m.groups()[2] or r'[^/]+')
        i = m.end()
      if i < len(val): yield esc(val[i:])
      if not partial: yield "$"
    return "".join(it(val))


class Request(object):
  """Request encapsulates the HTTP request info sent to your handler."""

  def __init__(self, environ):
    self.kwargs = {}  # updated when routing decision is calcuated
    self.environ = environ
    self.path = environ['PATH_INFO']
    self.method = environ['REQUEST_METHOD']
    self.fieldstorage = cgi.FieldStorage(environ=environ, fp=environ.get('wsgi.input', None))
    try:
      self.fields = {k: self.fieldstorage[k].value for k in self.fieldstorage}
    except TypeError:
      self.fields = {}
    hlist = [(k[5:].replace("_","-").title(), v) for k, v in environ.items() if k.startswith("HTTP_")]
    self.headers = wsgiref.headers.Headers(hlist)


class Response(object):
  """Response contains the status, headers, and content of an HTTP response.
  You return a Response object in your request handler. """

  def __init__(self, content=None, code=200, headers=None, **kwargs):
    self._default_headers = {}
    self.content = content or []
    self.code = code
    headers = headers or []
    self.headers = wsgiref.headers.Headers(list(getattr(headers, 'items', lambda: headers)()))

  def write(self, *content):
    self.content.extend(content)

  def towsgi(self, start_response):
    content = self.finalize() or self.content or []
    self.code = self.code or 500
    for h, v in self._default_headers.items(): self.headers.setdefault(h, str(v))
    start_response("%i %s" % (self.code, self.http_status()[0]), list(self.headers.items()))
    return content

  def http_status(self):
    return _http_status(self.code)

  def finalize(self):
    pass


class StringResponse(Response):
  def __init__(self, content=None, charset='utf-8', content_type='text/html', **kwargs):
    content = [content] if content else []
    Response.__init__(self, content=content, **kwargs)
    self.content_type = content_type
    self.charset = charset

  def finalize(self):
    out = ''.join(self.content).encode(self.charset)
    self._default_headers['content-type'] = "%s ;charset=%s" % (self.content_type, self.charset)
    self._default_headers['content-length'] = len(out)
    return (out,)


class JsonResponse(StringResponse):
  def __init__(self, val=None, sort_keys = True, **kwargs):
    self.val = val
    self.sort_keys = sort_keys
    self.json_args = kwargs.pop('json_args', {})
    kwargs.setdefault('content_type', 'application/json')
    StringResponse.__init__(self, **kwargs)

  def finalize(self):
    self.content = (json.dumps(self.val, sort_keys=self.sort_keys, **self.json_args),)
    return StringResponse.finalize(self)


class FileResponse(Response):
  def __init__(self, file, content_type=None, close=True, **kwargs):
    Response.__init__(self, **kwargs)
    self.close = close
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
    self.content = self.readandclose()  # content iterator, not list

  def readandclose(self):
    while True:
      dat = self.file.read(8192)
      if not dat:
        break
      yield dat
    if self.close:
      self.file.close()


class HttpError(Exception, StringResponse):
  """HttpError triggers your handle_STATUS handler if one is set."""

  def __init__(self, code=500, content="", **kwargs):
    Exception.__init__(self, "HTTP %i" % (code))
    StringResponse.__init__(self, content, code=code, **kwargs)


class App(Router):
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
    for _ in range(100):  # TTL sanity check
      fn, matched, kwargs = self._lookup_route(url, request.method, router)
      if not isinstance(fn, Router):
        request.kwargs.update(kwargs)
        return fn(request, response)
      request.kwargs.update(kwargs)
      url = "/" + url[len(matched):].lstrip("/")
      router = fn
    raise ValueError("Recursion limit hit on route lookup.")

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
      raise HttpError(
          405,
          headers={'Allow': ",".join(methods_allowed)})
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
      http_error.write("An error occurred:\n\n", http_error.traceback)
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
    return self._process_request(Request(environ)).towsgi(start_response)

  def _process_request(self, request):
    """Call the base request handler and get a response."""
    return self._get_response_handled(self.request_handler, request, StringResponse())

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
    sc = ThreadedWSGIServer if threaded else wsgiref.simple_server.WSGIServer
    return wsgiref.simple_server.make_server(host, port, self, server_class=sc)

  def serve_forever(self, port=8080, host='', threaded=True):
    print("Serving on %s:%s -- ctrl+c to quit." % (host, port))
    try: self.make_server(port, host, threaded).serve_forever()
    except KeyboardInterrupt: pass


class ThreadedWSGIServer(socketserver.ThreadingMixIn,
                          wsgiref.simple_server.WSGIServer):
  """Simple WSGI server with threading mixin"""
  daemon_threads = True