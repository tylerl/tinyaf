
import wsgiref.types
import wsgiref.simple_server
import contextlib
from dataclasses import InitVar, dataclass, field
import wsgiref.headers
import json
import re
import http
import html
import socketserver
import copy
import urllib.parse
import io

from . import util

import typing as t
_O = t.Optional
_T = t.TypeVar("_T")
Headers = wsgiref.headers.Headers
_AnyHeaders: t.TypeAlias = dict[str, str] | list[tuple[str, str]] | Headers
_Wrapper = t.Callable[[_T], _T]
_ResponseT = t.TypeVar("_ResponseT", bound="Response", covariant=True)

class HandlerFn(t.Protocol):
    def __call__(self, request: "Request", response: _ResponseT,  # type: ignore
                 /) -> t.Any: ...


@t.runtime_checkable
class Handler(t.Protocol):
    def handle_request(self, request: "Request", **kwargs) -> "Response": ...


AnyHandler = HandlerFn | Handler


class DataclassDefaultOverridable:  # subclass can override field defaults
    def __init_subclass__(cls, **kwargs) -> None:
        if dc_fields := getattr(cls, "__dataclass_fields__", None):
            for k, v in (cls.__dict__ | kwargs).items():
                if k in dc_fields:
                    dc_fields[k].default = v


@dataclass(kw_only=True)
class HttpError(Exception, DataclassDefaultOverridable):
    """Throwable HTTP Error."""
    code: int = field(kw_only=False, default=500)
    short: str | None = field(kw_only=False, default=None)
    desc: str | None = None
    headers: dict[str, str] = field(default_factory=dict)  # type:ignore

    def default_headers(self) -> dict[str, str]: return {}
    def all_headers(self): return self.default_headers() | self.headers
    def has_cause(self): return self.__cause__ is not None

    def exc_info(self):
        """Get the exception info tuple if this error was raised from an exception."""
        if self.has_cause():
            return (type(self.__cause__), self.__cause__, self.__traceback__)
        return (type(self), self, self.__traceback__)

    def causes(self):
        cause = self.__cause__
        seen = []  # circular reference prevention
        while cause:
            if cause in seen:
                break
            yield cause
            seen.append(cause)
            cause = cause.__cause__

    @classmethod
    @contextlib.contextmanager
    def wrap_exceptions(cls, *args, **kwargs):
        try:
            yield
        except HttpError as ex:
            raise ex
        except Exception as ex:
            raise cls(*args, **kwargs) from ex


@dataclass(kw_only=True)
class MethodNotAllowed(HttpError):
    code = 405
    allow: tuple[str,...] = field(default_factory=tuple)

    def default_headers(self):
        return {"Allow": ",".join(self.allow)}


@dataclass(kw_only=True)
class Redir(HttpError):
    code = 403
    location: str

    def default_headers(self):
        return {'Location': self.location}

@dataclass
class RouteMatch:
    route: "Route"
    match: re.Match[str]

@dataclass
class Request:
    environ: wsgiref.types.WSGIEnvironment
    path: str
    method: str
    headers: Headers
    route_match: RouteMatch

    # fieldstorage: cgi.FieldStorage  # TODO: cgi is deprecated and will be removed
    # fields: dict[str, t.Any]
    http_errors: tuple[HttpError, ...] = field(default_factory=tuple)

    # def _filebytes(self):
    #     pass

    # def _parse_fields(self, content_type, fp):
    #     # TODO: parsing out fields manually instead of using cgi module
    #     ct, args = util.parse_header_options(content_type, lower=True)
    #     if ct == "multipart/form-data":
    #         return _parse_multipart(fp)
    #     elif ct == 'application/x-www-form-urlencoded':
    #         return _parse_urlencoded(fp)

    @classmethod
    def from_wsgi(cls, environ: wsgiref.types.WSGIEnvironment):
        # fs = cgi.FieldStorage(
        #    environ=environ, fp=environ.get('wsgi.input', None))
        # fields = {k: fs[k].value for k in fs} if fs.list else {}
        hlist = [(k[5:].replace("_", "-").title(), v)
                 for k, v in environ.items() if k.startswith("HTTP_")]
        return cls(environ, environ['PATH_INFO'], environ['REQUEST_METHOD'],
                   Headers(hlist), cls._empty_match())

    def with_route(self, route_match: RouteMatch) -> t.Self:
        request = copy.copy(self)
        request.route_match = route_match
        # TODO: shorten path to reflect sub-match
        return request

    def with_error(self, http_error: HttpError) -> t.Self:
        request = copy.copy(self)
        request.http_errors = (http_error, *self.http_errors)
        return request

    @property
    def query_string(self) -> str:
        return self.environ.get("QUERY_STRING", "")

    @property
    def query_vars(self):
        return dict(urllib.parse.parse_qsl(self.query_string))

    @property
    def route_vars(self):
        return self.route_match.match.groupdict()

    @property
    def content_type(self) -> tuple[str, dict[str,str]]:
        return util.parse_header_options(self.headers.get('Content-Type',''))

    def _body_fp(self) -> t.Iterable[bytes]:
        return self.environ.get('wsgi.input', (b"",))

    def body_bytes(self) ->bytes:
        return b''.join(self._body_fp())

    @property
    def post_vars(self):
        if self.method != "POST":
            return {}
        ct, vars = self.content_type
        ct = ct.lower()
        vars = {k.lower():v for k,v in vars.items()}
        if ct[10:] == "multipart/":
            return _parse_multipart(self.body_bytes())
        elif ct == 'application/x-www-form-urlencoded':
            encoding = vars.get('content-encoding', 'latin1')
            dict(urllib.parse.parse_qsl(self.body_bytes(), encoding=encoding))
        return []

    @property
    def vars(self):
        return self.query_vars | self.route_vars

    @classmethod
    def _empty_match(cls) -> RouteMatch:
        try:
            return cls._empty_match_inst
        except AttributeError:
            match = t.cast(re.Match[str], re.match("/", "/"))
            cls._empty_match_inst = RouteMatch(Route("/"), match)
            return cls._empty_match_inst

@dataclass(kw_only=True)
class Response:
    """Response contains everything about the response but the content."""
    code: int = 200
    content_type: str | None = None
    charset: str | None = None
    h: InitVar[_AnyHeaders | None] = None
    headers: Headers = field(init=False, default=None)  # type:ignore
    http_error: HttpError | None = None

    def __post_init__(self, h: _AnyHeaders | None):
        self.headers = Headers(
            list(h.items()) if isinstance(h, dict) or isinstance(h, Headers)
            else h
        )
        self._resp_inst: t.Iterable[bytes] = tuple()
        if self.http_error and self.http_error.code:
            self.code = self.http_error.code

    def set_content(self, content: t.Any) -> None:
        """Called when the request handler returns a non-null result."""
        del content  # unused param
        raise ValueError(f'"{type(self).__name__}" does not implement '
                         'set_content but request handler returned a value.')

    def finalize(self, request: Request) -> bytes | None:
        """Do any post-request cleanup; return bytes if they're the content."""
        del request  # unused param
        return None

    def _http_status(self) -> str:
        """Get the HTTP status text for the current response code."""
        try:
            return http.HTTPStatus(self.code).phrase
        except ValueError:
            return "StatusPhraseUnknown"

    def _wsgi_start_response_args(self):
        """Get the args that will go to WSGI's start_response()."""
        status_line = f"{self.code} {self._http_status()}"
        headers = self.headers.items()
        if self.http_error and self.http_error.has_cause():
            return (status_line, headers, self.http_error.exc_info())
        return (status_line, self.headers.items(), None)

    def _apply_default_headers(self):
        """Set headers that cannonically apply to this response type."""
        if self.content_type:
            cs = f";charset={self.charset}" if self.charset else ""
            self.headers.setdefault('Content-Type', f"{self.content_type}{cs}")
        if self.http_error:
            for k, v in self.http_error.all_headers().items():
                self.headers.setdefault(k, v)

    def _wsgi_finalize(self, request: Request):
        """Finalize the response after the handler has run."""
        final = self.finalize(request)  # pylint: disable=assignment-from-none
        if final is not None:
            self._resp_inst = (final,) if isinstance(final, bytes) else final
        self._apply_default_headers()

    def _wsgi_response(self) -> t.Iterable[bytes]:
        return self._resp_inst


@dataclass(kw_only=True)
class StringResponse(Response):
    """A StringResponse manages string-to-bytes encoding for you."""
    content: InitVar[str | None] = field(default=None, kw_only=False)
    content_type: str = 'text/html'
    charset: str = 'utf-8'
    # __init__(self, content, *, code, h, content_type, charset)

    def __post_init__(self, h: _AnyHeaders | None, content: str | None):
        super().__post_init__(h)
        self._str_list: list[str] = [] if content is None else [content]

    def set_content(self, content: str | list[str]):
        self._str_list = [content] if isinstance(content, str) else content

    def write(self, content: str):
        self._str_list.append(content)

    def finalize(self, request: Request) -> bytes | None:
        return ''.join(self._str_list).encode(self.charset)


@dataclass(kw_only=True)
class JsonResponse(Response):
    content: t.Any = field(kw_only=False, default_factory=list)
    content_type: str = 'application/json'
    charset: str = 'utf-8'

    def set_content(self, content: t.Any):
        self.content = content

    def finalize(self, request: Request) -> bytes | None:
        return json.dumps(self.content).encode(self.charset)


@dataclass
class FuncHandler:
    handlerfn: HandlerFn
    response_class: type[Response]

    def handle_request(self, request: Request, **kwargs) -> Response:
        http_error = request.http_errors[0] if request.http_errors else None
        response = self.response_class(http_error=http_error)
        content = self.handlerfn(request, response)
        if content is not None:
            if isinstance(content, Response):
                if response.http_error and not content.http_error:
                    content.http_error = response.http_error
                return content
            response.set_content(content)
        return response


@dataclass
class Route:
    path: str
    methods: tuple[str] = tuple()
    pattern: re.Pattern = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'pattern', util.path_to_pattern(self.path))

    def match(self, request: Request) -> RouteMatch | None:
        if match := self.pattern.match(request.path):
            if self.methods and request.method not in self.methods:
                raise MethodNotAllowed(allow=self.methods)
            return RouteMatch(self, match)
        return None


class App:
    # TODO: Need to do error reporting
    DEFAULT_RESPONSE_CLASS = StringResponse

    def __init__(self):
        self.routes: list[tuple[Route, Handler]] = []
        self.errorhandlers: dict[int | type | None, Handler] = dict()

    # Decorators ----------------------------------------------------------

    def route(self, path, methods: _O[list[str]] = None, *,
              response_class: _O[type[Response]] = None) -> _Wrapper[HandlerFn]:
        def decorator(handlerfn: HandlerFn):
            self.add_route(path, handlerfn, methods, response_class)
            return handlerfn
        return decorator

    def errorhandler(self, code: int, *, response_class: _O[type[Response]] = None) -> _Wrapper[HandlerFn]:
        def decorator(handlerfn: HandlerFn):
            self.set_errorhandler(code, handlerfn, response_class)
            return handlerfn
        return decorator

    # Setup ---------------------------------------------------------------

    def add_route(self, path: str, handler: AnyHandler,
                  methods: _O[list[str]] = None,
                  response_class: _O[type[Response]] = None):
        self.routes.append((Route(path, tuple(methods) if methods else tuple()),
                            self.make_handler(handler, response_class=response_class)))

    def set_errorhandler(self, error: int | type | None,
                         handler: AnyHandler,
                         response_class: _O[type[Response]] = None):
        self.errorhandlers[error] = self.make_handler(
            handler, response_class=response_class)

    def make_handler(self, handler: AnyHandler, *, response_class: _O[type[Response]]) -> Handler:
        if isinstance(handler, Handler):
            if response_class:
                raise ValueError(
                    "Cannot set response_class unless handler is a callback function")
            return handler
        return FuncHandler(handler, response_class or self._response_class(handler))

    def _response_class(self, handlerfn: HandlerFn):
        resp_class = util.type_from_callable(handlerfn, 1)
        if resp_class and issubclass(resp_class, Response) and resp_class != Response:
            return resp_class
        return self.DEFAULT_RESPONSE_CLASS

    # Request Handling ----------------------------------------------------

    def handle_request(self, request: Request) -> Response:
        try:
            with HttpError.wrap_exceptions():
                route_match, handler = self.get_route(request)
                request = request.with_route(route_match)
                return handler.handle_request(request)
        except HttpError as http_error:
            if error_handler := self.get_error_handler(http_error):
                return error_handler.handle_request(request.with_error(http_error))
            raise

    def get_route(self, request: Request) -> tuple[RouteMatch, Handler]:
        methods_allowed = set([])
        for route, handler in self.routes:
            try:
                if match := route.match(request):
                    return match, handler
            except MethodNotAllowed as ex:
                methods_allowed = methods_allowed.union(ex.allow)
        if methods_allowed:
            raise MethodNotAllowed(allow=tuple(methods_allowed))
        raise HttpError(404)

    def get_error_handler(self, http_error: HttpError) -> Handler | None:
        for t in type(http_error).__mro__:  # Exception type handers
            if h := self.errorhandlers.get(t):
                return h
        for c in http_error.causes():  # handlers for causal exceptions
            if h := self.errorhandlers.get(type(c)):
                return h
        if h := self.errorhandlers.get(http_error.code):  # error code handler
            return h
        return self.errorhandlers.get(None)  # default handler

    def default_error_handler(self, request: Request) -> Response:
        if not request.http_errors:
            raise HttpError(
                500, "Error handler called with no error",
                desc="Error handler was invoked with no error attached to the "
                "request. (That is, itself, an error.)")
        err, *others = request.http_errors
        resp = StringResponse(http_error=err)
        resp.write(f"<h2>HTTP {resp.code} - {resp._http_status()}</h2>\n")
        if err.short:
            resp.write(f"<h3>{html.escape(err.short)}</h3>\n")
        if err.desc:
            resp.write(f"<div>{html.escape(err.desc)}</div>\n")
        else:
            # TODO: Something better here -- Need to figure out what to do in confusion
            resp.write(f"<pre>{html.escape(repr(err))}</pre>\n")
        return resp

    def fallback_error_handler(self, request: Request, http_error: HttpError) -> Response:
        try:
            with HttpError.wrap_exceptions():
                return self.default_error_handler(request.with_error(http_error))
        except HttpError as ex:
            return StringResponse(
                "The server encountered the following error:\n"
                f"HTTP({http_error.code}): {http_error.short}\n\n"
                f"During the handling another error was encountered.\n",
                http_error=http_error, content_type='text/plain')

    # Server Running ----------------------------------------------------

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

    def __call__(self, environ, start_response):
        """WSGI entrypoint."""
        request = Request.from_wsgi(environ)
        response = self._wsgi_get_response(request)
        response._wsgi_finalize(request)
        start_response(*response._wsgi_start_response_args())
        return response._wsgi_response()

    def _wsgi_get_response(self, request: Request) -> Response:
        """Call handler with 100% error handling."""
        try:
            with HttpError.wrap_exceptions():
                return self.handle_request(request)
        except HttpError as ex:  # pylint: disable=broad-exception-caught
            return self.fallback_error_handler(request, ex)
