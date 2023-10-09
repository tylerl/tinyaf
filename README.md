> _NOTE: A rewrite of this library is currently in progress. The original
  TinyAF was built long before type annotations were a thing, and back
  when Python 2/3 compatibility mattered. The new version fully embraces
  typing and aims to make ease-of-use and legibility a greater priority
  at the expense of having more lines of code._

# Tiny App Framework  (TinyAF)

TinyAF is an _exceptionally_ small Web Application Framework for Python WSGI.

This framework has no dependencies outside the standard library, and consists
of only about 300 lines of code.

## Seriously? But why?

The intended use case is building minimal, self-contained web application
servers. The framework is designed to make it perfectly reasonable to just
paste the contents of tinyaf.py into your own code, and ship a single small
file as your entire application.

Because copy-paste deployment is the primary expected use case, tinyaf.py
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

Here's a complete (though pointless) example. It's as easy to use as the
examples you see touted with all the other web frameworks. So given our
absurdly tight constraints, I'd call that a win.

```python
import tinyaf  # obviously you can just paste tinyaf.py here instead.

app = tinyaf.App()
@app.route("/")
def home(request, response):
  return "Hello world"

@app.route("/static/<filename>")
def static(request, response):
  try:
    return tinyaf.FileResponse(request['filename'])
  except OSError:
    raise tinyaf.HttpError(404)

@app.route("/api/<type>/<id:\d+>/list", response_class=tinyaf.JsonResponse)
def api_get(request, response):
  if not request.headers["api-key"] == "123":
    raise tinyaf.HttpError(403)
  response.headers["generator"] = "tiny/api"
  return {"type": request['type'], "id": request["id"] }

app.tracebacks_to_http = True  # show handler exceptions in our web output
app.serve_forever()
```