"""TinyAF is an exceptionally small Web Application Framework for Python WSGI."""
import cgi
import http
import json
import mimetypes
import os
import re
import socketserver
import sys
import traceback
import wsgiref.headers
import wsgiref.simple_server
import dataclasses

import typing
from typing import Callable, Any, TypeVar, Optional, TypedDict

from . import types

T = TypeVar("T")

RequestHandlerT = Callable[["Request", "Response"], T]
Environ = TypedDict("Environ", {
    'REQUEST_METHOD': str, 'SCRIPT_NAME': str,
})


@dataclasses.dataclass
class Route:
    path: str
    handler: RequestHandlerT | None
    methods: list[str] | None
    vars: dict[str, str] | None


class Router(object):
    """Manage routes and error handlers in your application.
    """

    def __init__(self):
        self.entries: list[dict] = []
        self.apps: list[App] = []

    def _router_update(self, **kwargs):
        self.entries.append(kwargs.copy())
        for app in self.apps:
            app._router_update(**kwargs)  # pylint: disable=W0212

    def route(self, path, handler=None, methods=None, **kwargs):  # additional: response_class, vars
        r"""Assign a handler function to a URL."""
        kwargs.update(dict(routetype='route', path=path, methods=methods))

        def decorator(func):
            self._router_update(handler=func, **kwargs)
            return func

        if handler:
            return decorator(handler)
        return decorator

    # additional: vars
    def errorhandler(self, code, handler: Optional[RequestHandlerT[Any]] = None, **kwargs):
        r"""Assign a handler function to a given status code."""
        kwargs.update(dict(routetype='errorhandler', code=code))

        def decorator(func):
            self._router_update(handler=func, **kwargs)
            return func

        if handler:
            return decorator(handler)
        return decorator


class Request(object):
    """Request objects contain all the information from the HTTP request."""

    def __init__(self, environ: dict[str, Any]):
        self.vars = {}  # populated when the routing decision is calcuated
        # updated to contain the re match object from the routing decision
        self._route_match = None
        self.environ = environ
        self.path = environ['PATH_INFO']
        self.method = environ['REQUEST_METHOD']
        self.fieldstorage = cgi.FieldStorage(
            environ=environ, fp=environ.get('wsgi.input', None))
        self.fields = {k: self.fieldstorage[k].value
                       for k in self.fieldstorage} if self.fieldstorage.list else {}
        self.headers = wsgiref.headers.Headers([(k[5:].replace("_", "-").title(), v)
                                                for k, v in environ.items() if k.startswith("HTTP_")])  # (eg:HTTP_CONTENT_TYPE -> Content-Type)

    def forward(self, application, env=None):
        """Send this request to a WSGI application.

        The application parameter must refer to a WSGI-compliant application. That
        is, it must be callable, and its parameters, return value, and behavior
        must be consistent with PEP 333 or PEP 3333.

        Args:
          application: WSGI-compliant object to send this request to.
          env: dictionary with additional/replacement environment components to use.

        Return:
          a Response object containing the result of the WSGI handler.
        """
        environ = self.environ.copy()
        if env:
            environ.update(env)
        # place to stick the response object in callback, else we lose it.
        _response = None

        def start_response(statusline, headers):
            nonlocal _response
            code, status = statusline.split(" ", 1)
            _response = Response(content=None, code=int(
                code), headers=headers, status=status)

        content = application(self.environ, start_response)
        if not _response:
            raise AssertionError("start_response not called.")
        _response.content = content
        return _response

    def __getitem__(self, key):
        try:
            return self.vars[key]
        except KeyError:
            return self.fields[key]

    def __contains__(self, key):
        return key in self.vars or key in self.fields


class Response:
    """Response contains everything about the response but the content."""

    def __init__(self, content=None, code=200, headers=None, status=None):
        self.response_instance = self  # override to send another object as the wsgi response
        self._default_headers = {}  # Headers that will apply if no competing headers are set
        self.status = status
        self.code = code
        headers = headers or []  # headers can be either a list of tuples or a dict
        self._wsgi_environ = None
        self.content = content
        self.headers = wsgiref.headers.Headers(
            list(getattr(headers, 'items', lambda: headers)()))

    def finalize(self):
        pass

    def set_content(self, content):
        self.content = content

    def _http_status(self):
        try:
            status = http.HTTPStatus(self.code)  # pylint: disable=E1120
            return status.phrase, status.description
        except ValueError:
            return "Unknown", ""

    def __iter__(self):
        return iter([] if self.content is None else self.content)

    def _do_finalize(self):
        result = self.finalize()  # pylint: disable=assignment-from-no-return
        if result is not None:
            self.content = result

    def _start_response_args(self):
        status_line = f"{self.code} {self.status or self._http_status()[0]}"
        return (status_line, list(self.headers.items()))

    def _finalize_wsgi(self, environ):
        self._wsgi_environ = environ
        self._do_finalize()
        self.code = self.code or 500
        for key, val in self._default_headers.items():
            self.headers.setdefault(key, str(val))


class WritableResponse(Response):
    """Rresponse with writable content."""

    def __init__(self, content=None, **kwargs):
        super().__init__(**kwargs)
        self.reset()
        if content:
            self.write(content)

    def reset(self):
        self.content = []

    def set_content(self, content):
        self.reset()
        self.write(content)

    def write(self, content):
        self.content.append(content)

    def finalize(self):
        pass


class StringResponse(WritableResponse):
    """A StringResponse manages string-to-bytes encoding for you."""
    DEFAULT_CONTENT_TYPE = 'text/html'

    def __init__(self, content=None, charset='utf-8', content_type=None, **kwargs):
        super().__init__(content=content, **kwargs)
        self.content_type = content_type
        self.charset = charset

    def finalize(self):
        out = ''.join(self.content).encode(self.charset)
        content_type = (self.content_type or self.DEFAULT_CONTENT_TYPE)
        self._default_headers['content-type'] = f"{content_type}; charset={self.charset}"
        self._default_headers['content-length'] = len(out)
        return (out, )


class JsonResponse(StringResponse):
    """A JsonResponse sends the provided value as JSON-encoded text.

    If a value is set in the constructor then it can be an object, and can be
    updated as `response.value`. Otherwise it will be initialized to an empty
    list, which can be appended to using `response.write()`.
    """
    DEFAULT_JSON_ARGS = {'sort_keys': True}
    DEFAULT_CONTENT_TYPE = 'application/json'

    def __init__(self, content=None, **kwargs):
        self.json_args = kwargs.pop('json_args', {})
        super().__init__(**kwargs)
        if content:
            self.set_content(content)

    def set_content(self, content):
        self.content = content

    def finalize(self):
        kwargs = self.DEFAULT_JSON_ARGS | self.json_args
        self.content = (json.dumps(self.content, **kwargs), )
        return super().finalize()


class FileResponse(Response):
    """A FileResponse sends raw files from your filesystem."""
    chunk_size = 32768

    def __init__(self, file, content_type=None, close=True, **kwargs):
        super().__init__(**kwargs)
        self.file: typing.IO[Any]
        self._close = close
        self.content_type = content_type

        if not hasattr(file, 'read'):
            file = open(file, 'rb')

        self.file = file

    def set_content(self, content):
        if self.file:
            self.close()
        if hasattr(content, 'read'):
            self.file = content
        else:
            self.file = open(content, 'rb')

    def finalize(self):
        if self.content_type:
            self._default_headers['content-type'] = self.content_type
        elif name := getattr(self.file, 'name', ''):
            self.content_type = mimetypes.guess_type(name)[0]

        self._default_headers['content-length'] = os.fstat(
            self.file.fileno()).st_size

        if 'wsgi.file_wrapper' in self._wsgi_environ:
            self.response_instance = self._wsgi_environ['wsgi.file_wrapper'](
                self.file, self.chunk_size)

    def close(self):
        if self._close and hasattr(self.file, 'close'):
            self.file.close()

    def __iter__(self):
        return iter(lambda: self.file.read(self.chunk_size), '')


class HttpError(Exception, StringResponse):
    """HttpError is a Response that you throw; it also invokes status handlers."""

    def __init__(self, code=500, content="", **kwargs):
        self.traceback = kwargs.pop("traceback", None)
        self.exception = kwargs.pop("exception", None)
        Exception.__init__(self, "HTTP %i" % (code))
        StringResponse.__init__(self, content, code=code, **kwargs)


class App(Router):
    response_class = StringResponse
    tracebacks_to_http = False
    tracebacks_to_stderr = True

    def __init__(self, router=None):
        super().__init__()
        self.routes = []
        self.errorhandlers = {}
        if router:
            router.apps.append(self)
            for d in router.entries:
                self._router_update(**d)

    ### Routing ###########################################
    def _router_update(self, routetype, **kwargs):
        if routetype == 'route':
            kwargs['pattern'] = re.compile(self._route_escape(kwargs['path']))
            self.routes.append(kwargs.copy())
        elif routetype == 'errorhandler':
            self.errorhandlers[int(kwargs['code'])] = kwargs.copy()

    @staticmethod
    def _route_escape(val):
        """Encode non-regex patterns as regex."""
        if val[0] == '^':
            return val  # indicates raw regex

        def esc(s): return re.escape(re.sub("//+", "/", "/" + s))

        def it(val):
            i = 0  # pattern below is "*" or "<identifier>" or "<identifier:regex>"
            # complicated because escaping > is allowed ("<ident:foo\>bar>")
            yield "^"
            for m in re.finditer(r'(<([a-zA-Z0-9\.]+)(?::((?:\\.|[^>])*))?>)|(\*)', val):
                if m.start() > i:
                    yield esc(val[i:m.start()])
                if m.group() == "*":
                    yield r"[^/]+"
                else:
                    yield "(?P<%s>%s)" % (m.groups()[1], m.groups()[2] or r'[^/]+')
                i = m.end()
            if i < len(val):
                yield esc(val[i:])
            yield "$"

        return "".join(it(val))

    def _lookup_route(self, request):
        """Figure out which URL matches."""
        methods_allowed = []
        for route in self.routes:
            match = re.match(route['pattern'], request.path)
            if match:
                methods = route.get('methods')
                if methods and request.method not in methods:
                    methods_allowed.extend(methods)
                    continue
                return route, match, match.groupdict()
        if methods_allowed:
            raise HttpError(405, headers={'Allow': ",".join(methods_allowed)})
        raise HttpError(404)

    ### Request Handling ###########################################
    def __call__(self, environ, start_response):
        """WSGI entrypoint."""
        resp = self._get_response_handled(
            self.request_handler, Request(environ), self.response_class())
        resp._finalize_wsgi(environ)
        start_response(*resp._start_response_args())
        return resp.response_instance

    def _get_response_handled(self, handler: RequestHandlerT[Any], request: Request, response: Response) -> Response:
        """Try/catch around _get_response(), calls error handler."""
        try:
            return self._get_response(handler, request, response)
        except HttpError as err:
            http_error = err
        except Exception as err:  # pylint: disable=broad-exception-caught
            http_error = HttpError(
                500, traceback=traceback.format_exc(), exception=err)
            if self.tracebacks_to_stderr:
                sys.stderr.write(http_error.traceback)
        if isinstance(response, HttpError):
            return self.nested_error(request, response, http_error)
        return self._get_response_handled(self.error_handler, request, http_error)

    def _get_response(self, handler: T_RequestHandler, request: Request, response: Response) -> Response:
        """Sort out the response/result ambiguity, and return the response."""
        result = handler(request, response)
        if result:
            if isinstance(result, Response):
                return result
            response.set_content(result)
        return response

    def request_handler(self, request, response):
        """Primary request handler; override for alternate top-level behavior."""
        return self.request_router(request, response)

    def request_router(self, request: Request, response: Response) -> Response:
        """Route and handle request (can raise HttpErrors)."""
        route, match, url_args = self._lookup_route(request)
        request.vars.update(url_args)
        request.vars.update(route.get('vars', {}))
        request._route_match = match
        if route.get('response_class'):
            response = route['response_class']()
        return route['handler'](request, response)

    def error_handler(self, request: Request, http_error: HttpError) -> Response:
        """Top-level error handler. Override to incercept every error."""
        route = self.errorhandlers.get(int(http_error.code))
        if route:
            return route['handler'](request, http_error)
        elif http_error.content:  # Bail if content is already set
            pass
        elif self.tracebacks_to_http and http_error.traceback:
            return self.traceback_handler(request, http_error)
        else:
            return self.generic_error_handler(request, http_error)

    def nested_error(self, request: Request, first_error: HttpError, second_error: HttpError) -> Response:
        """Handles the condition where an error occurs in an error handler."""
        del request
        content = (
            f"An error occurred:\n{first_error}\n\n",
            f"Then an error occurred in the error handler:\n{second_error}\n")
        code = first_error.code or second_error.code or 500
        code = 500 if code < 400 or code > 599 else code
        return HttpError(code, content,
                         exception=first_error.exception or second_error.exception,
                         traceback=first_error.traceback or second_error.traceback,
                         content_type='text/plain',
                         )

    def traceback_handler(self, request: Request, http_error: HttpError):
        """Handles attaching the traceback to an error response."""
        del request
        http_error.content_type = 'text/plain'
        http_error.write(f"\nAn error occurred:\n\n {http_error.traceback}\n")

    def generic_error_handler(self, request: Request, http_error: HttpError):
        """Error handler used when the app doesn't define an error handler."""
        http_error.content_type = 'text/html'
        phrase, description = http_error._http_status()
        http_error.write("<h1>HTTP %s - %s</h1>" % (http_error.code, phrase))
        http_error.write("<p>%s.</p>\n" %
                         (description or "Your request could not be processed"))
        if http_error.code == 405:
            http_error.write("<p><b>Methods allowed:</b> %s</p>\n" %
                             (http_error.headers['Allow']))
            http_error.write("<p><b>Method used:</b> %s</p>\n" %
                             (request.method))

     ### Running the Server ###########################################

    def make_server(self, port=8080, host='', threaded=True):
        svr = wsgiref.simple_server.WSGIServer
        if threaded:  # Add threading mix-in
            svr = type('ThreadedServer', (socketserver.ThreadingMixIn, svr),
                       {'daemon_threads': True})
        return wsgiref.simple_server.make_server(host, port, self, server_class=svr)

    def serve_forever(self, port=8080, host='', threaded=True):
        print("Serving on %s:%s -- ctrl+c to quit." % (host, port))
        try:
            self.make_server(port, host, threaded).serve_forever()
        except KeyboardInterrupt:
            pass
