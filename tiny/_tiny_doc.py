"""TinyAF is an exceptionally small Web Application Framework for Python WSGI."""

# _tiny_doc.py contains the docstrings from tiny.py, allowing us to spluge on
# exhaustive documentation for when we need it, without dropping a massive
# amount of content into everyone's copy-paste template.

# pylint: disable=W1401

class Router(object):
    """Manage routes and error handlers in your application."""
    def route(self, path, handler=None, methods=None, response_class=None, vars=None, **kwargs):
        r"""Assign a handler function to a URL.

        If `handler` is not provided, then this function returns a decorator which
        is expected to be applied to the URL handler.

        Handlers have the signature `name(request, response):` where `request` is
        a Request object, and `response` is derived from Response(). If your handler
        returns a new Response object, then the provided one will be discarded.
        Otherwise any content you return will be appended using response.write(...)

        Args:
            path: str
                The URL to map the handler to. The pattern is described below.
            handler: function(Request, Response)
                The function that will handle the web requests. If not provided,
                then a decorator will be returned.
            methods: list(string)
                An optional list of HTTP methods to associate with this mapping.
                If present, the mapping will *only* service matching HTTP methods.
            response_class: type(Response)
                A class derived from Response that will be provided as the "default"
                response to the handler.
            vars: dict(string: string)
                A set of key-value pairs to be set in the Request object passed
                to the handler.

        There are two kinds of patterns for URLs, "standard" patterns, and
        regex patterns. If the pattern does not start with a "^", then it's treated
        as a standard pattern, with the following rules:

        * Standard Patterns:

            1:  Unless otherwise specified, strings match exactly.
                Example: "/foo/bar" matches only the URL "/foo/bar".

            2:  The character "*" matches any non-empty string not containing "/".
                Example: "/hello/*/world" matches the URL "/hello/friendly/world".

                In technical terms, it's matched using r"[^/]+".

            3:  A string in the form "<foo>" matches the same pattern as
                in rule 2 (non-empty, not containing "/"), but saves the result into
                your request vars dict under the key named "foo".

                Example: "/hello/<adj>/world" matches the URL "/hello/friendly/world",
                and the vars dict contains {"adj": "friendly"}.

                In technical terms, "<([0-9A-Za-z.]+)>" becomes "(?P<\1>[^/]+)"

            4:  A string in the form "<foo:regex>" matches the pattern specified by
                regex, and stores that capture result under the key "foo".

                Technically: "<([0-9A-Za-z.]+):([^>]+)>" becomes r"(?P<\1>\2)"
                Except that you can also escape ">" as "\>" (e.g. "<id:foo\>bar>"),
                even though I can't imagine how that would be useful.

                Note that there is nothing built-in preventing you from matching "/"
                in your regex. So "/hello/<name:.*>.txt" will match "/hello/world.txt",
                but it will also happily match "/hello/my/name/is/jonas.txt", where
                the string "my/name/is/jonas" will be captured as "name".

                Example: "/foo/<bar:\d{3}-\d{4}>/baz" matches the URL "/foo/867-5309/baz"
                and vars will contain {"bar": "867-5309"}.

        * Regex Patterns

            If your pattern starts with "^", then it's treated as a raw regex, and
            matched as-is, with no second guessing or attempts at preventing you
            from shooting yourself in the foot. Any named capture groups in your pattern
            will result in their matches getting stored into the request's "vars"
            dictionary under the key named in your capture group. Regexes are matched
            using Python's re library. Named capture groups in Python regexes use the
            syntax "(?P<name>pattern)". Regex patterns are NOT anchored at the end
            unless you explicitly do so yourself so using a "$" suffix.

            For example, the pattern "^/[^/]+/world.txt" will match the URL
            "/hello/world.txt...plus/some/trash", because there's no trailing anchor.
            You'd probably want the pattern "^/[^/]+/world.txt$" instead, which will
            only match patterns like "/hello/world.txt" and "/howdy/world.txt".

        * Leading Slashes.

            Due to a quirk of HTTP, all URLs start with "/". All of them. This means
            that patterns that don't have a leading "/" will never match anything.
            The Standard pattern engine will helpfully prepend a "/" to every pattern
            that doesn't have one. So the pattern "hello/world" gets turned into
            "/hello/world".

            Regex patterns, though, match as-is. So the pattern "^hello/world" won't
            ever match anything. That's not to say that regex patterns without a leading
            slash never match: for example, "^.*\.html$" will match any URL ending
            in ".html", because .* can match leading slashes.
        """

    def errorhandler(self, code, handler=None, vars=None, **kwargs):
        r"""Assign a handler function to a given status code.

        If `handler` is not provided, then this function returns a decorator which
        is expected to be applied to the URL handler.

        The handler is associated with the numeric status code provided. Only
        one handler is allowed per code, so a newly-assigned handler will replace
        any existing handler for the same status code.

        Handlers have the signature `name(request, error):` where `request` is
        a Request object, and `error` is derived from HttpError(). Note that
        HttpError is already derived from StringResponse, so error handlers neatly
        parallel standard request handlers.

        If your handler is triggered by an exception (other than just HttpError),
        then error.exception will contain the original exception and error.traceback
        will contain the traceback text.
        
        If your handler returns a new Response object, then the provided one
        (the HttpError object) will be discarded. Otherwise any content you return
        will be appended using error.write(...).
        """

class Request(object):
    """Request encapsulates the HTTP request info sent to your handler."""


class Response(object):
    """Response contains the status, headers, and content of an HTTP response.
    You return a Response object in your request handler. """
