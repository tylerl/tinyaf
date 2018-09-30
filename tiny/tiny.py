import cgi
import functools
import fnmatch
import mimetypes
import os
import re
import sys
import traceback
import types
import wsgiref.headers

STATUS_MSGS = {200: 'OK', 303: 'See Other', 404: 'Not Found', 500: 'Error'}


class Router(object):
  def __init__(self):
    self.errorhandlers = {}
    self.routes = []

  def route(self, path, *methods):
    """Decorator which gives you a handler for a given path."""

    def decorator(fn):
      self.routes.append((path if path.startswith("^") else
                          fnmatch.translate(path), fn, methods))
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
      path = re.escape(path)
    self.routes.append((path, router, []))


class Request(object):
  """Request encapsulates the HTTP request info sent to your handler."""

  def __init__(self, environ):
    self.environ = environ
    self.path = environ['PATH_INFO']
    self.args = []
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

  def __init__(self, content=[], code=200, headers=None, **kwargs):
    self._default_headers = {}
    self.content = content
    self.code = code
    self.status = kwargs.get('status', None) or STATUS_MSGS.get(
        code, 'Code %i' % (code))
    headers = headers or []
    self.headers = wsgiref.headers.Headers(list(
        getattr(headers, 'items', lambda: headers)()))

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
  def __init__(self,
               content=u"",
               charset='utf-8',
               content_type='text/html',
               **kwargs):
    Response.__init__(self, content=[content], **kwargs)
    self.content_type = content_type
    self.charset = charset

  def append(self, content):
    self.content.append(content)

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
    self.content = self.readandclose()

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
    self.show_tracebacks = False

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
      fn, matched, args, kwargs = self._lookup_route(url, request.method,
                                                     router)
      if not isinstance(fn, Router):
        request.args.extend(args)
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

  def error_handler(self, request, error):
    """Top-level error handler. Override to incercept every error."""
    handler = self.router.errorhandlers.get(error.code,
                                            self._default_error_handler)
    return handler(request, error)

  def _default_error_handler(self, request, error):
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

  def __call__(self, environ, start_response):
    """WSGI entrypoint."""
    request = Request(environ)
    response = self._process_request(request)
    return response.towsgi(start_response)

  def _process_request(self, request):
    """Call the base request handler and get a response."""
    return self._get_response_handled(self.request_handler, request,
                                      StringResponse())

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
      return self._get_response_handled(self.error_handler, request, e)
    except Exception as e:
      err = HttpError(500)
      err.traceback = traceback.format_exc()
      err.exception = e
      sys.stderr.write(err.traceback)
      return self._get_response(self.error_handler, request, err)
