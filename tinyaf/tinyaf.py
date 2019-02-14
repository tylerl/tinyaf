import cgi
import json
import mimetypes
import os
import re
import sys
import traceback
import wsgiref.headers
import wsgiref.simple_server
if sys.version_info[0] == 2:  # py2      # pylint disable import error due to python version
    import SocketServer as socketserver  # pylint: disable=E0401
    import httplib                       # pylint: disable=E0401
else:  # py3
    import socketserver                  # pylint: disable=E0401
    import http                          # pylint: disable=E0401


class Router(object):
    """Manage routes and error handlers in your application."""
    def __init__(self):
        self.entries = []
        self.apps = []

    def _router_update(self, **kwargs):
        self.entries.append(kwargs.copy())
        for app in self.apps:
            app._router_update(**kwargs)

    def route(self, path, handler=None, methods=None, **kwargs):  # additional: response_class, vars
        kwargs.update(dict(routetype='route', path=path, methods=methods))
        def decorator(fn):
            self._router_update(handler=fn, **kwargs)
            return fn
        if handler: return decorator(handler)
        return decorator

    def errorhandler(self, code, handler=None, **kwargs):  # additional: vars
        kwargs.update(dict(routetype='errorhandler', code=code))
        def decorator(fn):
            self._router_update(handler=fn, **kwargs)
            return fn
        if handler: return decorator(handler)
        return decorator


class Request(object):
    """Request objects contain all the information from the HTTP request."""
    def __init__(self, environ):
        self.vars = {}  # populated when the routing decision is calcuated
        self._route_match = None  # updated to contain the re match object from the routing decision 
        self.environ = environ
        self.path = environ['PATH_INFO']
        self.method = environ['REQUEST_METHOD']
        self.fieldstorage = cgi.FieldStorage(environ=environ, fp=environ.get('wsgi.input', None))
        self.fields = {k: self.fieldstorage[k].value
                       for k in self.fieldstorage} if self.fieldstorage.list else {}
        hlist = [(k[5:].replace("_", "-").title(), v) for k, v in environ.items() if k.startswith("HTTP_")]
        self.headers = wsgiref.headers.Headers(hlist)

    def forward(self, application, env=None):
        environ = self.environ.copy()
        if env: environ.update(env)
        self.__response = None  # place to stick the response object in callback, else we lose it.
        def start_response(statusline, headers):
            code, status = statusline.split(" ", 1)
            self.__response = Response(content=None, code=int(code), headers=headers, status=status)
        content = application(self.environ, start_response)
        if not self.__response: raise AssertionError("start_response not called.")
        self.__response.content = content
        return self.__response

    def __getitem__(self, key):
        try:
            return self.vars[key]
        except KeyError:
            return self.fields[key]

    def __contains__(self, key):
        return key in self.vars or key in self.fields


class Response(object):
    """Response objects manage translating your output to WSGI."""
    def __init__(self, content=None, code=200, headers=None, **kwargs):
        self.response_instance = self  # override to send another object as the wsgi response
        self._default_headers = {}  # Headers that will apply if no competing headers are set
        self.content = content or []
        self.status = kwargs.get('status', None)
        self.code = code
        headers = headers or []  # headers can be either a list of tuples or a dict
        self.headers = wsgiref.headers.Headers(list(getattr(headers, 'items', lambda: headers)()))

    def _finalize_wsgi(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        self.content = self.finalize() or self.content or []
        self.code = self.code or 500
        for h, v in self._default_headers.items():
            self.headers.setdefault(h, str(v))
        self.start_response("%i %s" % (self.code, self.status or self.http_status()[0]),
                            list(self.headers.items()))

    def write(self, content):
        self.content.append(content)

    def finalize(self):
        pass

    def __iter__(self):
        return iter(self.content)

    def http_status(self):
        if sys.version_info[0] == 2:
            return httplib.responses.get(self.code, 'Unknown'), ""
        else:
            try:
                s = http.HTTPStatus(self.code)  # pylint: disable=E1120
                return s.phrase, s.description
            except ValueError:
                return "Unknown", ""


class StringResponse(Response):
    """A StringResponse manages string-to-bytes encoding for you."""
    def __init__(self, content=None, charset='utf-8', content_type='text/html', **kwargs):
        content = [content] if content else []
        Response.__init__(self, content=content, **kwargs)
        self.content_type = content_type
        self.charset = charset

    def finalize(self):
        out = ''.join(self.content).encode(self.charset)
        self._default_headers['content-type'] = "%s; charset=%s" % (self.content_type, self.charset)
        self._default_headers['content-length'] = len(out)
        return (out, )


class JsonResponse(StringResponse):
    """A JsonResponse sends the provided val as JSON-encoded text."""
    def __init__(self, val=None, sort_keys=True, **kwargs):
        self.val = val
        self.sort_keys = sort_keys
        self.json_args = kwargs.pop('json_args', {})
        kwargs.setdefault('content_type', 'application/json')
        StringResponse.__init__(self, **kwargs)

    def write(self, val):
        self.val = val

    def finalize(self):
        self.content = (json.dumps(self.val, sort_keys=self.sort_keys, **self.json_args), )
        return StringResponse.finalize(self)


class FileResponse(Response):
    """A FileResponse sends raw files from your filesystem."""
    chunk_size = 32768
    def __init__(self, file, content_type=None, close=True, **kwargs):
        Response.__init__(self, **kwargs)
        self._close = close
        if not hasattr(file, 'read'):
            file = open(file, 'rb')
        if not content_type and hasattr(file, 'name'):
            content_type = mimetypes.guess_type(file.name)[0]
        if content_type:
            self._default_headers['content-type'] = content_type
        if hasattr(file, 'fileno'):
            self._default_headers['content-length'] = "%i" % (os.fstat(file.fileno()).st_size)
        self.file = file

    def finalize(self):
        if 'wsgi.file_wrapper' in self.environ:
            self.response_instance = self.environ['wsgi.file_wrapper'](self.file, self.chunk_size)

    def close(self):
        if self._close and hasattr(self.file, 'close'): self.file.close()

    def __iter__(self):
        return iter(lambda: self.file.read(self.chunk_size), '')


class HttpError(Exception, StringResponse):
    """HttpError is a Response that you throw; it also invokes status handlers."""

    def __init__(self, code=500, content="", **kwargs):
        Exception.__init__(self, "HTTP %i" % (code))
        StringResponse.__init__(self, content, code=code, **kwargs)


class App(Router):
    response_class = StringResponse
    tracebacks_to_http = False
    tracebacks_to_stderr = True

    def __init__(self, router=None):
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
        esc = lambda s: re.escape(re.sub("//+", "/", "/" + s))

        def it(val):
            i = 0       # pattern below is "*" or "<identifier>" or "<identifier:regex>"
            yield "^"   # complicated because escaping > is allowed ("<ident:foo\>bar>")
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
        resp = self.request_handler(Request(environ))
        resp._finalize_wsgi(environ, start_response)
        return resp.response_instance

    def request_handler(self, request):
        """Top-level request handler."""
        return self._get_response_handled(self._route_request, request, self.response_class())

    def _route_request(self, request, response):
        """Route and handle request (can raise HttpErrors)."""
        route, match, url_args = self._lookup_route(request)
        request.vars.update(url_args)
        if route.get('vars'):
            request.vars.update(route['vars'])
        request._route_match = match
        if route.get('response_class'):
            response = route['response_class']()
        return route['handler'](request, response)

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
            if self.tracebacks_to_stderr:
                sys.stderr.write(http_error.traceback)
            return self._get_response(self.error_handler, request, http_error)

    def _get_response(self, fn, request, response):
        """Sort out the response/result ambiguity, and return the response."""
        result = fn(request, response)
        if result:
            if isinstance(result, Response): response = result
            else: response.write(result)
        return response

    def error_handler(self, request, http_error):
        """Top-level error handler. Override to incercept every error."""
        route = self.errorhandlers.get(int(http_error.code))
        if route:
            return route['handler'](request, http_error)
        return self._default_error_handler(request, http_error)

    def _default_error_handler(self, request, http_error):
        if http_error.content:  # Bail if content is already set
            return
        if self.tracebacks_to_http and hasattr(http_error, 'traceback'):
            http_error.headers['Content-type'] = 'text/plain'
            http_error.write("An error occurred:\n\n %s" % (http_error.traceback))
            return
        http_error.headers['Content-type'] = 'text/html'
        phrase, description = http_error.http_status()
        http_error.write("<h1>HTTP %s - %s</h1>" % (http_error.code, phrase))
        http_error.write("<p>%s.</p>\n" % (description or "Your request could not be processed"))
        if http_error.code == 405:
            http_error.write("<p><b>Methods allowed:</b> %s</p>\n" % (http_error.headers['Allow']))
            http_error.write("<p><b>Method used:</b> %s</p>\n" % (request.method))

    def make_server(self, port=8080, host='', threaded=True):
        svr = wsgiref.simple_server.WSGIServer
        if threaded:  # Add threading mix-in
            svr = type('ThreadedServer', (socketserver.ThreadingMixIn, svr), {'daemon_threads': True})
        return wsgiref.simple_server.make_server(host, port, self, server_class=svr)

    def serve_forever(self, port=8080, host='', threaded=True):
        print("Serving on %s:%s -- ctrl+c to quit." % (host, port))
        try:
            self.make_server(port, host, threaded).serve_forever()
        except KeyboardInterrupt:
            pass
