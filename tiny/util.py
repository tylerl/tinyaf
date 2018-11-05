import html
import pprint

from . import tiny

app = tiny.App()


@app.route("/dump.{fmt:(txt|json)}")
def dump_request(req, resp):
    out = dict(
        environ={k: v
                 for k, v in req.environ.items() if isinstance(v, str)},
        fields=req.fields,
        headers=dict(req.headers.items()),
        method=req.method,
        path=req.path,
    )

    fmt = req.kwargs.get('fmt', 'txt')
    if fmt == 'json':
        return tiny.JsonResponse(out)

    if fmt == 'txt':
        resp.content_type = 'text/plain'
        pprint.pprint(out, stream=resp)


@app.route("/")
def home(req, resp):
    return """
  <p><a href="/dump.txt">dump.txt</a>
  <p><a href="/dump.json">dump.json</a>
  """


def main():
    app.route("/")
    app.serve_forever()


if __name__ == '__main__':
    main()
