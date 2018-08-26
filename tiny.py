import cgi
import re
import sys
import traceback
import types
import wsgiref.headers

_STATUS_MSGS = {200: 'OK', 303: 'See Other', 404: 'Not Found', 500: 'Error'}
UNICODE = getattr(__builtins__, 'unicode', str)  # python 2/3
FILETYPE = type(sys.stdin)


class Request(object):
  """Request encapsulates the HTTP request info sent to your handler."""

  def __init__(self, environ):
    self.environ = environ
    self.path = environ['PATH_INFO']
    self.args = []
    self.method = environ['REQUEST_METHOD']
    # preserve cgi-style fieldstorage in case you need it
    self.fieldstorage = cgi.FieldStorage(
        environ=environ, fp=environ.get('wsgi.input', None))
    # but coelesce down to a dict for typical use
    self.fields = {k: self.fieldstorage[k].value for k in self.fieldstorage}
    self.headers = wsgiref.headers.Headers([(k[5:], v)
                                            for k, v in environ.items()
                                            if k.startswith("HTTP_")])


class Response(object):
  """Response contains the status, headers, and content of an HTTP response.
  You return a Response object in your request handler. """

  def __init__(self, code=200, headers=None, content=None, status=None):
    self.code = code
    self.binary = False
    if headers:
      if hasattr(headers, 'items'):
        self.headers = wsgiref.headers.Headers(list(headers.items()))
      else:
        self.headers = wsgiref.headers.Headers(list(headers))
    else:
      self.headers = wsgiref.headers.Headers(list())
    self.content = [] if content is None else content
    self.status = status


class HttpError(Exception, Response):
  """HttpError triggers your handle_STATUS handler if one is set."""

  def __init__(self, code=500, headers=None, content=None, status=None):
    Exception.__init__(self, "HTTP %i" % (code))
    Response.__init__(self, code, headers, content, status)


class App(object):

  def __init__(self):
    self.routes = []
    self.handlers = {}
    self.show_tracebacks = False

  def route(self, path_regex, *methods):
    """Decorator which gives you a handler for a given path regex."""

    def wrapper(fn):
      self.routes.append((path_regex, fn, methods))
      return fn

    return wrapper

  def handler(self, code):
    """Decorator which gives you a handler for a given HttpError status."""

    def wrapper(fn):
      self.handlers[code] = fn
      return fn

    return wrapper

  def __call__(self, environ, start_response):
    """WSGI entrypoint. Handles WSGI pecularity."""
    request = Request(environ)
    response = self._process_request(request)
    status = response.status or _STATUS_MSGS.get(response.code, 'Unknown')
    if (isinstance(response.status, list) or
        isinstance(response.status, tuple) or
        isinstance(response.status, types.GeneratorType)):
      content = response.content
    else:
      content = [response.content]
    if not response.binary:
      content = (
          s.encode("utf-8") for s in content if isinstance(s, UNICODE))
    start_response("%i %s" % (response.code, status),
                   list(response.headers.items()))
    return content

  def _get_response(self, fn, request, response):
    """Sort out the response/result ambiguity, and return the response."""
    result = fn(request, response)
    if result:
      if isinstance(result, Response):
        response = result
      else:
        response.content = result
    return response

  def _get_response_handled(self, fn, request, response):
    """Try/catch on a response fetcher, call error handler."""
    try:
      return self._get_response(fn, request, response)
    except HttpError as e:
      return self._get_response_handled(self.handle_error, request, e)
    except Exception as e:
      err = HttpError(500)
      err.traceback = traceback.format_exc()
      err.exception = e
      sys.stderr.write(err.traceback)
      return self._get_response(self.handle_error, request, err)

  def _process_request(self, request):
    """Call the base request handler and get a response."""
    return self._get_response_handled(self.request_handler, request, Response())

  def request_handler(self, request, response):
    """Top-level request handler. Override to intercept every request."""
    methods_allowed = []
    for pattern, fn, methods in self.routes:
      match = re.match(pattern, request.path)
      if match:
        if methods and request.method not in methods:
          methods_allowed.extend(methods)
          continue
        request.args = match.groups()
        return fn(request, response)
    if methods_allowed:
      raise HttpError(
          405,
          status="Method not Allowed",
          headers={'Allow': ",".join(methods_allowed)})
    raise HttpError(404)

  def handle_error(self, request, error):
    """Top-level error handler. Override to incercept every error."""
    handler = self.handlers.get(error.code, self.default_error_handler)
    return handler(request, error)

  def default_error_handler(self, request, error):
    if error.content:  # Bail if content is already set
      return
    if self.show_tracebacks and hasattr(error, 'traceback'):
      error.headers['Content-type'] = 'text/plain'
      return ["An error occurred:\n\n", error.traceback]
    error.headers['Content-type'] = 'text/html'
    out = []
    if error.status == "Unknown":
      out.append("<h1>HTTP %i</h1>" % (error.code))
    else:
      out.append("<h1>HTTP %i - %s</h1>" % (error.code, error.status))
    out.append("<p>Your request could not be processed.</p>")
    if error.code == 405:
      out.append("<p><b>Methods allowed:</b> %s</p>" % (error.headers['Allow']))
      out.append("<p><b>Method used:</b> %s</p>" % (request.method))
    return out


##################
## Sample App

app = App()


@app.route(r'/$')
def home(req, resp):
  resp.headers['content-type'] = 'text/html'
  return "<html><h1>Hello World</h1>"


@app.route(r'/static/([^/.][^/]*)$')
def static(req, resp):
  import os
  import mimetypes
  filename = os.path.join(os.path.dirname(__file__), req.args[0])
  if not os.path.exists(filename):
    raise HttpError(404)
  mime, _ = mimetypes.guess_type(filename)
  if mime:
    resp.headers['content-type'] = mime
  f = open(filename)  # Open file before returning for error handling.

  def out(f):  # generator: defer fileio for memory reasons, ensure close at end
    while True:  # py3 simplifies: yield from iter(lambda: f.read(1024), '')
      buf = f.read(1024)
      if not buf:
        break
      yield buf
    f.close()

  return out(f)  # return generator which outputs file contents


def main():
  import wsgiref.simple_server
  try:
    import socketserver
  except ImportError:
    import SocketServer as socketserver

  class ThreadedWSGIServer(socketserver.ThreadingMixIn,
                           wsgiref.simple_server.WSGIServer):
    pass

  app.show_tracebacks = True
  server = wsgiref.simple_server.make_server(
      '', 8000, app, server_class=ThreadedWSGIServer)
  #server = wsgiref.simple_server.make_server('', 8000, app)
  print("Running on localhost:8000")
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass


if __name__ == '__main__':
  main()