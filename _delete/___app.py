from dataclasses import dataclass, field
import re
import socketserver
import typing as t
import wsgiref.simple_server

from ..tinyaf import util

Any = t.Any
T = t.TypeVar("T")
T_co = t.TypeVar("T_co", covariant=True)


# TODO: Remove this disable
# pylint: disable=missing-class-docstring, disable=missing-function-docstring

class App(router.Router):
    # ---- Routing and Decison-making  ------------------------------------
    DEFAULT_RESPONSE_CLASS: type[Response] = StringResponse

    def _make_response(self, route_match: router.RouteMatch):
        cls = route_match.route.response_class or self.DEFAULT_RESPONSE_CLASS
        return cls()

    def _default_error_handler(self, request: Request, response: HttpError):
        return f"Default error handler for: {response.code}"

    def _get_error_handler(self, request: Request, http_error: HttpError):
        return self.errorhandlers.get(http_error.code, self._default_error_handler), http_error

    def _handle_nested_error(self, request: Request, outer: HttpError, inner: HttpError) -> Response:
        # TODO: implement this
        raise NotImplementedError()

    # ---- Invocation / Request Processing  -------------------------------

    def _invoke_handler(self, handler: router._RequestHandler, request: Request, response: Response):
        """Sort out the return-vs-response and coelesce into Response."""
        content = handler(request, response)
        if content is not None:
            if isinstance(content, Response):
                return content
            response.set_content(content)
        return response

    def _handle_request(self, request: Request) -> Response:
        """Call the request handler and sort out error handling."""
        try:
            with HttpError.wrap_exceptions():
                route_match = self._route_match(request)
                request._set_route(route_match)
                response = self._make_response(route_match)
                return self._invoke_handler(route_match.route.handler, request, response)
        except HttpError as http_error:
            try:
                with HttpError.wrap_exceptions():
                    handler, response = self._get_error_handler(
                        request, http_error)
                    return self._invoke_handler(handler, request, response)
            except HttpError as nested:  # pylint: disable=broad-exception-caught
                return self._handle_nested_error(request, http_error, nested)

    def __call__(self, environ, start_response):
        """WSGI entrypoint."""
        request = Request(environ)
        response = self._handle_request(request)
        response_args = response._wsgi_finalize(request)
        start_response(*response_args)
        return response._wsgi_response()

    # ---- Running the Server  --------------------------------------------

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
