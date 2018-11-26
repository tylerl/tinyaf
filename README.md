# Tiny App Framework

TinyAF is an _exceptionally_ small Web Application Framework for Python WSGI.

This framework has no dependencies outside the standard library, and consists
of only about 300 lines of code.

## Seriously? But why?

The intended use case is building minimal, self-contained web application
servers. The framework is designed to make it perfectly reasonable to just
paste the contents of tiny.py into your own code, and ship a single small
file as your entire application.

Because copy-paste deployment is the primary expected use case, tiny.py
is highly optimized for code size. Each potential feature is balanced against
the space required to code that feature. But the design is also intended to
capture all the most important framework expectations, so that you don't
really miss the features you're missing from more comprehensive frameworks,
like Flask, Django, or Bottle.

The intended result is that TinyAF is precisely as minimal an app framework as
reasonably tolerable. If Django is a dump truck, Flask a motorcycle, and Bottle
a motorized bicycle, then TinyAF is really good skateboard.

## OK, but why?

This app framework was originally embedded as part of another application.
Design constraints prevented me from bringing in a "real" app framework, and
using raw WSGI is seriously a PITA, so I just coded up the simplest framework
I was willing to tolerate, inline.

Once having a zero-dependency, 300-line app framework became an option, I started
finding uses for it all over the place.

Since then, I've factored the framework out into its own repository and given it a
name, and it's gone through several revisions and complete rewrites, resulting in what
you see here.

## Fine then. How do I use it?

Here's a complete (though pointless) example. But it's as easy to use as the
examples you see touted with all the other web frameworks. So given our
absurdly tight constraints, I'd call that a win.

```python
import tiny  # obviously you can just paste tiny.py here instead.

app = tiny.App()
@app.route("/")
def home(request, response):
  return "Hello world"

@app.route("/static/<filename>")
def static(request, response):
  try:
    return tiny.FileResponse("./" + request['filename'])
  except OSError:
    raise tiny.HttpError(404)

@app.route("/api/<type>/<id:\d+>/list", response_class=tiny.JsonResponse)
def api_get(request, response):
  if not request.headers["api-key"] == "123":
    raise tiny.HttpError(403)
  response.headers["generator"] = "tiny/api"
  return {"type": request['type'], "id": request["id"] }

app.tracebacks_to_http = True  # show handler exceptions in our web output
app.serve_forever()
```