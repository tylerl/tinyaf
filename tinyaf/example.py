import os

import tinyaf

app = tinyaf.App()


@app.route(r'/')
def home(request, response):
    return "<html><h1>Hello World</h1></html>"


@app.route('/sleep/<seconds:\d>')
def sleepy_dave(request, response):
    import time
    time.sleep(int(request['seconds']))
    return "Slept %i sec" % (int(request['seconds']))


@app.route(r'/crash')
def crashy(req, resp):
    raise Exception("BOOM")


def forward(location, code=301):
    def handler(request, response):
        r = tinyaf.StringResponse()
        return tinyaf.Response('', code, {'location': location})
    return handler


app.route("/files")(forward('/files/', 302))


@app.route("/files/")
def dirlist(request, response):
    for f in os.listdir():
        if not f.startswith(".") and os.path.isfile(f):
            response.write("<a href=\"{0}\">{0}<a/><br/>\n".format(f))


@app.route('/files/<name>')
def files(req, resp):
    if not os.path.exists(req['name']):
        raise tinyaf.HttpError(404)
    return tinyaf.FileResponse(req['name'])


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
