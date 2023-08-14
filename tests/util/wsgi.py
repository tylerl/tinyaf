import typing as t
from urllib import parse
import io
import json
import wsgiref.types
import types

_unquote = parse.unquote
WSGIApplication = wsgiref.types.WSGIApplication

BASE_ENV = {
    'CONTENT_LENGTH': '',
    'GATEWAY_INTERFACE': 'CGI/1.1',
    'REMOTE_ADDR': '127.0.0.1',
    'REMOTE_HOST': 'localhost',
    'SCRIPT_NAME': '',
    'SERVER_NAME': 'TestServer/0',
    'SERVER_PORT': '8080',
    'SERVER_SOFTWARE': 'FakeHTTP/0',
    'wsgi.errors': None,  # out
    'wsgi.input': None,  # in
    'wsgi.multiprocess': False,
    'wsgi.multithread': False,
    'wsgi.run_once': False,
    'wsgi.url_scheme': 'http',
    'wsgi.version': (1, 0),
}

ExcInfo: t.TypeAlias = tuple[type[BaseException],
                             BaseException, types.TracebackType]
OptExcInfo: t.TypeAlias = ExcInfo | tuple[None, None, None]


class RequestFailure(AssertionError):
    """Something went wrong with the WSGI protocol interaction."""


class Request(object):
    def __init__(self, path,
                 postdata: str | bytes | None = None,
                 method: str | None = None,
                 env: dict | None = None):
        self.env = BASE_ENV.copy()
        self.path = path
        self.postdata = (
            postdata.encode() if isinstance(postdata, str)
            else postdata if postdata
            else b''
        )
        self.method = method or ('POST' if self.postdata else 'GET')
        self.env['REMOTE_HOST'] = 'localhost'
        self.env['SERVER_PROTOCOL'] = 'HTTP/1.1'
        self.env['REQUEST_METHOD'] = self.method
        if '?' in path:
            path, self.query = path.split('?', 1)
        else:
            self.query = ''
        self.path = _unquote(path)
        self.env['PATH_INFO'] = self.path
        self.env['QUERY_STRING'] = self.query
        if self.postdata:
            self.env['CONTENT_LENGTH'] = len(self.postdata)
        self.env.update(env or {})

    def _environ(self):
        env = self.env.copy()
        env['wsgi.input'] = io.BytesIO(self.postdata)
        env['wsgi.errors'] = io.BytesIO()
        return env

    def get_response(self, app: wsgiref.types.WSGIApplication):
        expecting_reponse = True
        resp_info = {}

        def _unused_write(b: bytes):
            pass

        def start_response(s: str, h: list[tuple[str, str]], exc=None):
            if expecting_reponse:
                resp_info.update(dict(status=s, headers=h, exc_info=exc))
            else:
                raise RequestFailure(
                    "start_response called at an unexpected moment")
            return _unused_write

        out = app(self._environ(), start_response)  # Invoke app handler
        expecting_reponse = False
        if not resp_info:  # Make sure start_reponse was called before return
            raise RequestFailure(
                "start_response not called before handler returned")
        outlist = list(iter(out))  # coelesce down to list
        # WSGI expects byte type only; no objects, unicode, iterators, etc.
        if not all(type(x) == bytes for x in outlist):  # pylint: disable=unidiomatic-typecheck
            types = list(set(type(x).__name__ for x in outlist))
            raise RequestFailure(
                f"Expected only type bytes in response. Got types {types}")
        return Response(self, outlist, **resp_info)

    def __repr__(self):
        return _repr_helper(self, ['path','query','method'])


class Response:
    encoding = 'utf-8'

    def __init__(self, request:Request, output: list[bytes],
                 status: str, headers: list[tuple[str, str]], exc_info: OptExcInfo | None = None):
        self.request = request
        self.output_list = output
        self.headers = headers
        self.exec_info = exc_info
        self.status_line = status
        try:
            code, stat = status.split(" ", 1)
            self.status = stat
            self.code = int(code)
        except ValueError as exc:
            raise RequestFailure(f"Invalid status line '{status}'") from exc
        self.headers_normalized = {}
        for k, v in headers:
            k = k.lower()
            if existing := self.headers_normalized.get(k):
                v = ", ".join((existing, v))
            self.headers_normalized[k] = v

    def dump(self):
        head = "\n".join(
            [f"HTTP/1.1 {self.status_line}"] +
            [f"{k}: {v}" for k, v in self.headers] +
            ["", ""]
        )
        return head + self.output_str()

    def output_bytes(self):
        return b''.join(self.output_list)

    def output_str(self, encoding=None):
        return self.output_bytes().decode(encoding or self.encoding)

    def output_json(self, validate=True):
        content_type, params = _parse_header(
            self.headers_normalized.get("content-type", ""))
        encoding = params.get('encoding', 'utf-8')
        if validate:
            assert "application/json" == content_type
        return json.loads(self.output_str(encoding))

    def __repr__(self):
        return _repr_helper(self, ['code','request'])


def _repr_helper(inst, attrs):
    kv = {k:getattr(inst,k) for k in attrs}
    vals = [f"{k}={v!r}" for k,v in kv.items() if v]
    return f"{inst.__class__.__qualname__}({', '.join(vals)})"

def _parseparam(s):
    while s[:1] == ';':
        s = s[1:]
        end = s.find(';')
        while end > 0 and (s.count('"', 0, end) - s.count('\\"', 0, end)) % 2:
            end = s.find(';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        yield f.strip()
        s = s[end:]


def _parse_header(line):
    """Parse a Content-type like header.

    Return the main content-type and a dictionary of options.

    """
    parts = _parseparam(';' + line)
    key = parts.__next__()
    pdict = {}
    for p in parts:
        i = p.find('=')
        if i >= 0:
            name = p[:i].strip().lower()
            value = p[i+1:].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
                value = value.replace('\\\\', '\\').replace('\\"', '"')
            pdict[name] = value
    return key, pdict