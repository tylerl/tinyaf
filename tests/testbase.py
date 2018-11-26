import cgi
import json
import unittest
import sys
import functools
import urllib
import io

import tiny

try:
    from urlparse import unquote  # PY3
except ImportError:
    from urllib.parse import unquote  # PY2

if sys.version_info[0] == 2:  # PY2
    BYTE_TYPE = str
else:  # PY3
    BYTE_TYPE = bytes

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


class RequestFailure(AssertionError):
    """Something went wrong with the WSGI protocol interaction."""


class Request(object):
    def __init__(self, path, postdata=None, method=None, env=None):
        self.env = BASE_ENV.copy()
        self.postdata = postdata
        if isinstance(self.postdata, str):
            self.postdata = self.postdata.encode('utf-8')
        self.env['REMOTE_HOST'] = 'localhost'
        self.env['SERVER_PROTOCOL'] = 'HTTP/1.1'
        self.env['REQUEST_METHOD'] = method or ('POST' if self.postdata else 'GET')
        if '?' in path:
            path, query = path.split('?', 1)
        else:
            path, query = path, ''
        self.env['PATH_INFO'] = unquote(path)
        self.env['QUERY_STRING'] = query
        if self.postdata:
            self.env['CONTENT_LENGTH'] = len(self.postdata)
        self.env.update(env or {})

    def _environ(self):
        env = self.env.copy()
        env['wsgi.input'] = io.BytesIO(self.postdata)
        env['wsgi.errors'] = io.BytesIO()
        return env

    def get_response(self, app):
        expecting_reponse = True
        resp_info = {}

        def start_response(stat, headers):
            if expecting_reponse:
                resp_info.update(dict(status=stat, headers=headers))
            else:
                raise RequestFailure("start_response called at an unexpected moment")

        out = app(self._environ(), start_response)  # Invoke app handler
        expecting_reponse = False
        if not resp_info:  # Make sure start_reponse was called before return
            raise RequestFailure("start_response not called before handler returned")
        outlist = list(iter(out))  # coelesce down to list
        # WSGI expects byte type only; no objects, unicode, iterators, etc.
        if not all(type(x) == BYTE_TYPE for x in outlist):
            types = list(set(type(x).__name__ for x in outlist))
            raise RequestFailure(
                "Expected only type %s in response. Got types %s" % (BYTE_TYPE.__name__, types))
        return Response(outlist, **resp_info)


class Response(object):
    encoding = 'utf-8'

    def __init__(self, output, status, headers):
        self.output_list = output
        self.headers_list = headers
        self.headers_dict = dict(headers)
        try:
            code, stat = status.split(" ", 1)
            self.code = int(code)
            self.status = stat
        except ValueError:
            raise RequestFailure("Invalid status line '%s'", status)

    def output(self):
        return functools.reduce(lambda a, b: a + b, self.output_list, BYTE_TYPE())

    def output_str(self, encoding=None):
        return self.output().decode(encoding or self.encoding)

    def output_json(self, validate=True):
        content_type, params = cgi.parse_header(self.headers_dict.get("content-type", ""))
        encoding = params.get('encoding', 'utf-8')
        if validate and content_type != "application/json":
            raise AssertionError(
                "expected content-type: application/json, got '%s'" % (content_type))
        return json.loads(self.output_str(encoding))


class TinyAppTestBase(unittest.TestCase):
    def assertDictFuzzy(self, subset, dictionary, msg=None):
        """Assert dict subset, but ignoring case on keys."""
        dictionary = {k.upper(): v for k, v in dictionary.items()}
        dictionaryFiltered = {}
        for k in subset:
            try:
                dictionaryFiltered[k] = dictionary[k.upper()]
            except KeyError:
                pass
        self.assertEqual(subset, dictionaryFiltered, msg)

    def assertResponseHeaders(self, resp, headers_dict, msg=None):
        return self.assertDictFuzzy(headers_dict, resp.headers_dict, msg)

    def assertResponse(self, resp, code, content=None, msg=None):
        if code != resp.code:
            msg = self._formatMessage(msg, 'expected HTTP %r, got HTTP %r' % (code, resp.code))
            raise self.failureException(msg)
        if content is not None:
            output = resp.output_str()
            self.assertEqual(content, output, msg=self._formatMessage(msg, 'contents differ'))

    def assertJsonResponse(self, resp, obj, msg=None):
        self.assertResponse(resp, 200)
        output = resp.output_json()
        self.assertEqual(obj, output, msg=self._formatMessage(msg, 'contents differ'))

    def assertJsonDictFuzzy(self, resp, obj, msg=None):
        self.assertResponse(resp, 200)
        output = resp.output_json()
        self.assertDictFuzzy(obj, output, msg)

    def assertProducesResponse(self, app, url, code, content=None, msg=None, **argv):
        msg = ("url(%s)" % (url)) + (" : %s" % (msg) if msg else "")
        resp = Request(url, **argv).get_response(app)
        self.assertResponse(resp, code, content, msg)
        return resp

    def assertProducesJson(self, app, url, obj, msg=None, fuzzy=False, **argv):
        msg = ("url(%s)" % (url)) + (" : %s" % (msg) if msg else "")
        resp = Request(url, **argv).get_response(app)
        if fuzzy:
            self.assertJsonDictFuzzy(resp, obj, msg)
        else:
            self.assertJsonResponse(resp, obj, msg)
        return resp


# import contextlib
# import sys
# import pdb
# import bdb
# #@contextlib.contextmanager
# def debugged(*commands):
#     def wrapper(*l,**k):
#       p = pdb.Pdb()
#       p.reset()
#       p.rcLines.extend(commands)
#       p.execRcLines()
#       #sys.settrace(p.trace_dispatch)
#       try:
#           yield p
#       except bdb.BdbQuit:
#           pass
#       finally:
#           p.quitting = True
#           sys.settrace(None)
