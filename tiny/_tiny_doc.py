#Contains the docstrings from tiny.py, keeping tiny.py short.


class Router(object):
    """Manage routes and error handlers in your application. """
    def route(self, path, handler=None, methods=None, response_class=None, vars=None, **kwargs):
        """Assign a handler function to a URL.

        If `handler` is not provided, then this function returns a decorator which
        is expected to be applied to the URL handler.

        Args:
            path: str
                The URL to map the handler to. The pattern is described below.
            handler: function(Request, Response)
                The function that will handle the web requests. If not provided,
                then a decorator will be returned.
            methods: list(string)
                An optional list of HTTP methods to associate with this mapping.
                If present, the mapping will *only* service matching HTTP methods.
            response_class: type(Resposne)
                A class derived from Response that will be provided as the "default"
                response to the handler.
            vars: dict(string: string)
                A set of key-value pairs to be set in the Request object passed
                to the handler.

        URL Patterns. The following pattern conventions are used.

        * "/foo/bar/baz"
            This matches the url /foo/bar exactly.
        * "/foo/{name}/baz"
            This matches any string for

        """

    def errorhandler(self, code, handler=None, **kwargs):  # additional: vars
        pass

class Request(object):
    """Request encapsulates the HTTP request info sent to your handler."""


class Response(object):
    """Response contains the status, headers, and content of an HTTP response.
    You return a Response object in your request handler. """
