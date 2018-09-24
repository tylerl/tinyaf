import unittest
import sys
import functools
import urllib

from . import tiny

if sys.version_info[0] == 2:  # PY2
  BYTE_TYPE = bytes
else:  # PY3
  BYTE_TYPE = str

BASE_ENV = {
  'SERVER_NAME': 'TestServer/0',
  'SERVER_SOFTWARE': 'FakeHTTP/0',
  'GATEWAY_INTERFACE': 'CGI/1.1',
  'SERVER_PORT': '8080',
  'REMOTE_HOST': '',
  'CONTENT_LENGTH': '',
  'SCRIPT_NAME': '',
  'REMOTE_HOST': 'localhost',
  'REMOTE_ADDR': '127.0.0.1',

  'wsgi.input': None, # in
  'wsgi.errors': None, # out

  'wsgi.version': (1,0),
  'wsgi.url_scheme': 'http',
  'wsgi.multithread': False,
  'wsgi.multiprocess': False,
  'wsgi.run_once': False,
}


class RequestFailure(AssertionError):
  """Something went wrong with the WSGI protocol interaction."""


class Request(object):
  def __init__(self, path, method='GET', version='HTTP/1.1', host='localhost', postdata=None, **env):
    self.env = BASE_ENV.copy()
    self.env.update(dict(
      SERVER_PROTOCOL=version,
      REQUEST_METHOD=method,
    ))
    if '?' in path:
        path,query = path.split('?',1)
    else:
        path,query = path,''
    self.env['PATH_INFO'] = urllib.parse.unquote(path, 'iso-8859-1')
    self.env['QUERY_STRING'] = query
    if postdata:
      self.env['CONTENT_LENGTH'] = len(postdata)

    # TODO: stringio on wsgi.input and wsgi.errors

    self.env.update(env)



  def _environ(self):
    pass

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
      raise RequestFailure("Expected only type %s in response. Got types %s",
                           BYTE_TYPE.__name__, types)
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


class WsgiAppTest(unittest.TestCase):
  def test_foo(self):
    self.assertEqual(True, True)


if __name__ == '__main__':
  unittest.main()
