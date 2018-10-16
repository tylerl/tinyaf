import cgi
import fnmatch
import functools
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
except ImportError:
  import SocketServer as socketserver  # py2

STATUS_MSGS = {200: 'OK', 303: 'See Other', 404: 'Not Found', 500: 'Error'}


class Router(object):
  def __init__(self):
    self.errorhandlers = {}
    self.routes = []

  def route(self, path, *methods):
    """Decorator which gives you a handler for a given path."""

    def decorator(fn):
      self.routes.append((path if path.startswith("^") else self._escape("/" + path), fn, methods))
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
    def it(val):
      i=0
      yield "^"
      for m in re.finditer(r'(\*)|(\{[a-zA-Z0-9]+\})', val):
        if m.start() > i: yield re.escape(val[i:m.start()])
        if m.group() == "*": yield r"[^/]+"
        else: yield "(?P<%s>[^/]+)" % (m.group()[1:-1])
        i = m.end()
      if i < len(val): yield re.escape(val[i:])
      if not partial: yield "$"
    return "".join(it(re.sub("//+", "/", val)))


class Request(object):
  """Request encapsulates the HTTP request info sent to your handler."""

  def __init__(self, environ):
    self.environ = environ
    self.path = environ['PATH_INFO']
    self.kwargs = {}
    self.method = environ['REQUEST_METHOD']
    self.fieldstorage = cgi.FieldStorage(
        environ=environ, fp=environ.get('wsgi.input', None))
    try:
      self.fields = {k: self.fieldstorage[k].value for k in self.fieldstorage}
    except TypeError:
      self.fields = {}
    hl = [(k[5:], v) for k, v in environ.items() if k.startswith("HTTP_")]
    self.headers = wsgiref.headers.Headers(hl)


class Response(object):
  """Response contains the status, headers, and content of an HTTP response.
  You return a Response object in your request handler. """

  def __init__(self, content=None, code=200, headers=None, **kwargs):
    self._default_headers = {}
    self.content = content or []
    self.code = code
    self.status = kwargs.get('status', None) or STATUS_MSGS.get(
        code, 'Code %i' % (code))
    headers = headers or []
    self.headers = wsgiref.headers.Headers(list(
        getattr(headers, 'items', lambda: headers)()))

  def append(self, *content):
    self.content.extend(content)

  def towsgi(self, start_response):
    content = self.finalize() or self.content or []
    code = self.code or 500
    status = self.status or STATUS_MSGS.get(code, 'Code %i' % (code))
    for h, v in self._default_headers.items():
      self.headers.setdefault(h, str(v))
    start_response("%i %s" % (code, status), list(self.headers.items()))
    return content

  def finalize(self):
    pass


class StringResponse(Response):
  def __init__(self, content=None, charset='utf-8', content_type='text/html', **kwargs):
    content = [content] if content else []
    Response.__init__(self, content=content, **kwargs)
    self.content_type = content_type
    self.charset = charset

  def finalize(self):
    if self.content_type:
      self._default_headers[
          'content-type'] = "%s;charset=%s" % (self.content_type, self.charset)
    out = ''.join(self.content).encode(self.charset)
    self._default_headers['content-length'] = len(out)
    return (out,)


class FileResponse(Response):
  def __init__(self, file, content_type=None, close=True, **kwargs):
    Response.__init__(self, **kwargs)
    self.close = close
    if not hasattr(file, 'read'):
      file = open(file, "rb")
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
      fn, matched, args, kwargs = self._lookup_route(url, request.method, router)
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
        return fn, match.group(0), match.groups(), match.groupdict()
    if methods_allowed:
      raise HttpError(
          405,
          status="Method not Allowed",
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
      http_error.append("An error occurred:\n\n", http_error.traceback)
      return
    http_error.headers['Content-type'] = 'text/html'
    if http_error.status == "Unknown":
      http_error.append("<h1>HTTP %i</h1>" % (http_error.code))
    else:
      http_error.append("<h1>HTTP %i - %s</h1>" % (http_error.code, http_error.status))
    http_error.append("<p>Your request could not be processed.</p>")
    if http_error.code == 405:
      http_error.append("<p><b>Methods allowed:</b> %s</p>" % (http_error.headers['Allow']))
      http_error.append("<p><b>Method used:</b> %s</p>" % (request.method))

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
        response.append(result)
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
    sc = ThreadedWSGIServer if threaded else  wsgiref.simple_server.WSGIServer
    return wsgiref.simple_server.make_server(host, port, self, server_class=sc)

class ThreadedWSGIServer(socketserver.ThreadingMixIn,
                          wsgiref.simple_server.WSGIServer):
  """Simple WSGI server with threading mixin"""
  daemon_threads = True