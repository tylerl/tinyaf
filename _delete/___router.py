from dataclasses import dataclass, field
import functools
import re
import typing as t

from ..tinyaf import util
from ..tinyaf.core import *

# TODO: Remove this disable
# pylint: disable=missing-class-docstring, disable=missing-function-docstring

T = t.TypeVar("T")
T_co = t.TypeVar("T_co", covariant=True)
T_contra = t.TypeVar("T_contra", contravariant=True)

# _Handler = t.Callable[[Request, Response[T]], None | T | Response]
_ResponseT = t.TypeVar("_ResponseT", bound=Response)
_ContentT = t.TypeVar("_ContentT")

_Wrapper = t.Callable[[T], T]
_RequestHandler = t.Callable[[Request, _ResponseT], None | Response |  t.Any]


@dataclass(frozen=True)
class Route(t.Generic[_ResponseT, _ContentT]):
    """Route!!"""
    path: str
    pattern: str = field(init=False)
    handler: _RequestHandler
    methods: tuple[str] = tuple()
    response_class: None | type[Response] = None

    def __post_init__(self):
        object.__setattr__(self, 'pattern', util.path_to_pattern(self.path))
        if self.response_class is None:
            resp_class = util.type_from_callable(self.handler, 1)
            if resp_class and issubclass(resp_class, Response) and resp_class != Response:
                object.__setattr__(self, 'response_class', resp_class)


@dataclass
class RouteMatch:
    route: Route
    match: re.Match[str]
    args: dict[str, str]

class Router:

    def __init__(self):
        self.routes: list[Route] = []
        self.errorhandlers: dict[int, _RequestHandler] = dict()

    def route(self, path, *,
              methods: None | list[str] = None,
              response_class: None | type[_ResponseT] = None
              ) -> _Wrapper[_RequestHandler[_ResponseT, _ContentT]]:

        def decorator(handler: _RequestHandler[_ResponseT, _ContentT]):
            print(f"Route: {path} -> {handler}")
            self.add_route(path, handler, methods, response_class)
            return handler
        return decorator

    def add_route(self, path: str, handler: _RequestHandler[_ResponseT, _ContentT],
                  methods: None | list[str] = None,
                  response_class: None | type[_ResponseT] = None):
        methods_tuple = tuple(methods) if methods else tuple()
        self.routes.append(Route(path, handler, methods_tuple, response_class))

    def set_errorhandler(self, code: int, handler: _RequestHandler):
        self.errorhandlers[code] = handler

    def errorhandler(self, code: int) -> _Wrapper[_RequestHandler]:
        def decorator(handler: _RequestHandler):
            self.set_errorhandler(code, handler)
            return handler
        return decorator

    def _route_match(self, request: Request):
        methods_allowed = []
        for route in self.routes:
            match = re.match(route.pattern, request.path)
            if match:
                if route.methods and request.method not in route.methods:
                    methods_allowed.extend(route.methods)
                    continue
                return RouteMatch(route, match, match.groupdict())
        if methods_allowed:
            raise HttpError(405, h={'Allow': ",".join(methods_allowed)})
        raise HttpError(404)
