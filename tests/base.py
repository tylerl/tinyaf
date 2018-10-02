import unittest
import sys
import functools
import urllib
import io

import tiny

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
  def __init__(self, path, **argv):
    self.env = BASE_ENV.copy()
    self.postdata = argv.get('postdata', None)
    if isinstance(self.postdata, str):
      self.postdata = self.postdata.encode('utf-8')
    self.env['REMOTE_HOST'] = argv.get('host', 'localhost')
    self.env['SERVER_PROTOCOL'] = argv.get('version', 'HTTP/1.1')
    self.env['REQUEST_METHOD'] = argv.get('method','POST' if self.postdata else 'GET')
    if '?' in path:
      path, query = path.split('?', 1)
    else:
      path, query = path, ''
    self.env['PATH_INFO'] = urllib.parse.unquote(path, 'iso-8859-1')
    self.env['QUERY_STRING'] = query
    if self.postdata:
      self.env['CONTENT_LENGTH'] = len(self.postdata)
    self.env.update(argv.get('env', {}))

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
    outlist = list(out)  # coelesce down to list
    # WSGI expects byte type only; no objects, unicode, iterators, etc.
    if not all(type(x) == BYTE_TYPE for x in outlist):
      types = list(set(type(x).__name__ for x in outlist))
      raise RequestFailure("Expected only type %s in response. Got types %s" %
                           (BYTE_TYPE.__name__, types))
    return Response(outlist, **resp_info)


class Response(object):
  encoding = 'utf-8'

  def __init__(self, output, status, headers):
    self.output_list = output
    self.headers = headers
    self.headers_dict = dict(headers)
    try:
      code, stat = status.split(" ", 1)
      self.code = int(code)
      self.status = stat
    except ValueError:
      raise RequestFailure("Invalid status line '%s'", status)

  def output(self):
    return functools.reduce(lambda a, b: a + b, self.output_list, BYTE_TYPE())

  def output_str(self):
    return self.output().decode(self.encoding)

class TinyAppTestBase(unittest.TestCase):
  def assertResponse(self, resp, code, content=None, msg=None):
    if code != resp.code:
      msg = self._formatMessage(msg, 'expected HTTP %r, got HTTP %r' % (code, resp.code))
      raise self.failureException(msg)
    if content is not None:
      output = resp.output_str()
      assertion_func = self._getAssertEqualityFunc(content, output)
      assertion_func(content, output, msg=msg)

  def assertProducesResponse(self, app, url, code, content=None, msg=None, **argv):
    msg = ("url(%s)" % (url)) + (" : %s" % (msg) if msg else "")
    resp = Request(url, **argv).get_response(app)
    self.assertResponse(resp, code, content, msg)


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
