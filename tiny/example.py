import os

from . import tiny

app = tiny.App()

@app.route(r'/$')
def home(req, resp):
  return "<html><h1>Hello World</h1></html>"

@app.route(r'/sleep/(\d+)$')
def sleepy_dave(req, resp):
  #TODO: debug fact that this doesn't dump stacktrace to output
  import time
  time.sleep(int(req.args[0]))
  return "Slept"

@app.route(r'/crash$')
def crashy(req, resp):
  #TODO: debug fact that this doesn't dump stacktrace to output
  raise Exception("BOOM")

@app.route(r'/files/$')
def dirlist(req, resp):
  for f in os.listdir():
    if os.path.isfile(f):
      resp.append("<a href=\"{0}\">{0}<a/><br/>\n".format(f))

@app.route(r'/files/([^/.][^/]*)$')
def files(req, resp):
  if not os.path.exists(req.args[0]):
    raise tiny.HttpError(404)
  return tiny.FileResponse(req.args[0])

def run():
  import wsgiref.simple_server
  app.show_tracebacks = True
  server = wsgiref.simple_server.make_server('', 8000, app)
  print("Running on localhost:8000")
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass

###################################################
# SCRATCH
#################
# if (isinstance(response.content, list) or
#     isinstance(response.content, tuple) or
#     isinstance(response.content, types.GeneratorType)):
#   content = response.content
# else:
#   content = [response.content]
# if not response.binary:  # auto-encode unicode
#   content = (
#       s.encode("utf-8") if isinstance(s, type(u'')) else s for s in content)
