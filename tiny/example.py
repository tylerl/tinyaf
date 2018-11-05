import os

from . import tiny

app = tiny.App()


@app.route(r'/')
def home(req, resp):
    return "<html><h1>Hello World</h1></html>"


@app.route(r'^/sleep/(\d+)$')
def sleepy_dave(req, resp):
    import time
    time.sleep(int(req.args[0]))
    return "Slept %i sec" % (int(req.args[0]))


@app.route(r'/crash')
def crashy(req, resp):
    raise Exception("BOOM")


fh = tiny.Router()


@fh.route("/")
def dirlist(req, resp):
    for f in os.listdir():
        if not f.startswith(".") and os.path.isfile(f):
            resp.append("<a href=\"{0}\">{0}<a/><br/>\n".format(f))


@fh.route(r'^/([^/.][^/]*)$')
def files(req, resp):
    if not os.path.exists(req.args[0]):
        raise tiny.HttpError(404)
    return tiny.FileResponse(req.args[0])


app.route("/files")(lambda a, b: tiny.Response('', 302, {'location': '/files/'}))
app.mount("/files/", fh)


def run():
    app.tracebacks_to_http = True
    server = app.make_server()
    print("Running on %s:%s. Ctrl+C to exit." % server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()

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
