
import wsgiref.simple_server
try:
  import socketserver  # py3
except ImportError:
  import SocketServer as socketserver  # py2


class ThreadedWSGIServer(socketserver.ThreadingMixIn,
                          wsgiref.simple_server.WSGIServer):
  """Simple WSGI server with threading mixin"""
  daemon_threads = True

def make_server(app, port=8080, host='', threaded=True):
  sc = ThreadedWSGIServer if threaded else  wsgiref.simple_server.WSGIServer
  return wsgiref.simple_server.make_server('', 8000, app, server_class=sc)
