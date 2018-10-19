from __future__ import absolute_import

from . import base
import tiny


class RouteTest(base.TinyAppTestBase):
  def test_exact_route(self):
    """Verify non-regex routes aren't regex or prefix matched."""
    app = tiny.App()
    app.route("/")(lambda req,resp: "A")
    app.route("/fo.")(lambda req,resp: "B")
    app.route("/bar")(lambda req,resp: "X")

    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/fo.", 200, "B")
    self.assertProducesResponse(app, "/foo", 404)
    self.assertProducesResponse(app, "/bar/foo", 404)
    self.assertProducesResponse(app, "/foo/bar", 404)

  def test_fuzzy_route(self):
    """Test non-regex pattern matching."""
    app = tiny.App()
    app.route("/")(lambda req,resp: "A")
    app.route("/*/bar")(lambda req,resp: "B")
    app.route("/foo/*/baz")(lambda req,resp: "C")

    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/foo/bar", 200, "B")
    self.assertProducesResponse(app, "/far/bar", 200, "B")
    self.assertProducesResponse(app, "/foo/far/baz", 200, "C")
    self.assertProducesResponse(app, "//bar", 404)
    self.assertProducesResponse(app, "/foo/far", 404)

  def test_regex_route(self):
    """Verify regex routes are regex matched."""
    app = tiny.App()
    app.route(r"^/$")(lambda req,resp: "A")
    app.route(r"^/fo.$")(lambda req,resp: "B")
    app.route(r"^/bar")(lambda req,resp: "pfx")

    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/foo", 200, "B")
    self.assertProducesResponse(app, "/bar/foo", 200, "pfx")
    self.assertProducesResponse(app, "/foo/bar", 404)

  def test_error_handler(self):
    """Verify custom error handlers get called, even on implicit (404) Errors."""
    app = tiny.App()
    app.route(r"/")(lambda req,resp: "OK")
    app.errorhandler(404)(lambda req,resp: "NOT OK")
    app.errorhandler(567)(lambda req,resp: "OTHER")
    @app.route("/other")
    def _(i,o):
      raise tiny.HttpError(567)

    self.assertProducesResponse(app, "/", 200, "OK")
    self.assertProducesResponse(app, "/foo", 404, "NOT OK")
    self.assertProducesResponse(app, "/other", 567, "OTHER")

  def test_method_miss(self):
    """Verify 405s error generated for method not found."""
    app = tiny.App()
    app.route(r"/", 'GET')(lambda req,resp: "/@G")
    app.route(r"/", 'POST')(lambda req,resp: "/@P")
    app.route(r"/gp", 'GET', 'POST')(lambda req,resp: "/gp@GP")
    app.route(r"/g", 'GET')(lambda req,resp: "/g@G")
    app.route(r"/p", 'POST')(lambda req,resp: "/p@P")
    # check routing
    self.assertProducesResponse(app, "/", 200, "/@G", postdata=None)
    self.assertProducesResponse(app, "/", 200, "/@P", postdata='foo!')
    self.assertProducesResponse(app, "/gp", 200, "/gp@GP", postdata=None)
    self.assertProducesResponse(app, "/g", 200, "/g@G", postdata=None)
    self.assertProducesResponse(app, "/p", 200, "/p@P", postdata='foo')
    # check headers
    resp = base.Request('/g',postdata='foo').get_response(app)
    self.assertResponse(resp, 405)
    self.assertEqual(resp.headers_dict['Allow'], 'GET')
    resp = base.Request('/p',postdata=None).get_response(app)
    self.assertResponse(resp, 405)
    self.assertEqual(resp.headers_dict['Allow'], 'POST')
    # check multi-method header result
    resp = base.Request('/',method='OPTIONS').get_response(app)
    self.assertResponse(resp, 405)
    self.assertEqual(resp.headers_dict['Allow'], 'GET,POST')

  def test_separate_router(self):
    """Verify that external routers can be supplied to an app."""
    r = tiny.Router()
    r.route("/")(lambda req,resp: "A")
    r.route(r"^/pf.x$")(lambda req,resp: "B")
    r.errorhandler(404)(lambda req,resp: "Z")
    app = tiny.App(router=r)
    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/pf0x", 200, "B")
    self.assertProducesResponse(app, "/nofind", 404, "Z")
    # and then complicate by adding another route and validating old ones
    r.route("/bar")(lambda req,resp: "C")
    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/pf0x", 200, "B")
    self.assertProducesResponse(app, "/nofind", 404, "Z")
    self.assertProducesResponse(app, "/bar", 200, "C")

  def test_bind_router(self):
    """Verify that bind routes get routed to."""
    r1 = tiny.Router()
    r2 = tiny.Router()
    app = tiny.App()
    r1.route("/a")(lambda req,resp: "A")
    r1.route("/b")(lambda req,resp: "B")
    r2.route("/c")(lambda req,resp: "C")
    r2.route("/d")(lambda req,resp: "D")
    app.mount('/pfx', r1)
    app.mount('/fpx', r2)
    r1.mount('/alias/', r2)
    self.assertProducesResponse(app, "/a", 404)
    self.assertProducesResponse(app, "/pfx", 404)
    self.assertProducesResponse(app, "/pfx/", 404)
    self.assertProducesResponse(app, "/pfx/c", 404)
    self.assertProducesResponse(app, "/pfx/a", 200, "A")
    self.assertProducesResponse(app, "/pfx/b", 200, "B")
    self.assertProducesResponse(app, "/fpx/c", 200, "C")
    self.assertProducesResponse(app, "/fpx/d", 200, "D")
    self.assertProducesResponse(app, "/pfx/alias/c", 200, "C")

  def test_bind_router_deep(self):
    """Make sure that binding nested routers works even if there's lots of them."""
    DEPTH = 60  # 100 is our depth max at the moment; not guarateed to be constant

    # with Nodes along the way
    r = app = tiny.App()
    r.route("/_node")(lambda req, resp: "Node: 0")
    for i in range(DEPTH):
      rnext = tiny.Router()
      rnext.route("/_node")(lambda req, resp: "Node: %i" % (i))
      r.mount("/x", rnext)
      r = rnext
    for i in range(DEPTH):
      url = "/".join([''] + ["x"] * i + ['_node'])
      self.assertProducesResponse(app, url, 200, "Node: %i" % (i), msg="Node %i" % (i))

    # without nodes along the way
    r = app = tiny.App()
    for i in range(DEPTH):
      rnext = tiny.Router()
      r.mount("/x", rnext)
      r = rnext
    r.route("/_node")(lambda req, resp: "Node: %i" % (DEPTH))
    url = "/".join([''] + ["x"] * DEPTH + ['_node'])
    self.assertProducesResponse(app, url, 200, "Node: %i" % (DEPTH))

  def test_bind_router_loop(self):
    """Make sure we crash out with a self-referential bind loop."""
    # Note: if this goes poorly, there's a chance of an infinite loop on this test.
    app = tiny.App()
    app.mount("/", app)
    app.tracebacks_to_stderr = False
    self.assertProducesResponse(app, "/", 500)

  def test_route_kwargs(self):
    handler = lambda req,rsp: " ".join("[%s]=[%s]" % (k,req.kwargs[k]) for k in sorted(req.kwargs))
    app = tiny.App()
    app.route("/a/{aa}")(handler)
    app.route("/a/{aa}/{bb}.html")(handler)
    app.route("/a/{aa}/{cc}.zip")(handler)
    app.route(r"^/b/(?P<dd>[^/]+)/(?P<whatever>.*)")(handler)
    app.route("/c/{aa:ba.}/")(handler)
    app.route("/d/{zz:.*}")(handler)

    self.assertProducesResponse(app, "/a/", 404)
    self.assertProducesResponse(app, "/a/hello", 200, "[aa]=[hello]")
    self.assertProducesResponse(app, "/a/world/", 404)
    self.assertProducesResponse(app, "/a/hello/world.html", 200, "[aa]=[hello] [bb]=[world]")
    self.assertProducesResponse(app, "/a/hello/world.zip", 200, "[aa]=[hello] [cc]=[world]")
    self.assertProducesResponse(app, "/b/what/ev/er...", 200, "[dd]=[what] [whatever]=[ev/er...]")

    self.assertProducesResponse(app, "/c/bar/", 200, "[aa]=[bar]")
    self.assertProducesResponse(app, "/c/foo/", 404)
    self.assertProducesResponse(app, "/d/foo/bar/baz", 200, "[zz]=[foo/bar/baz]")


  def test_kwargs_with_bind(self):
    handler = lambda req,rsp: " ".join("[%s]=[%s]" % (k,req.kwargs[k]) for k in sorted(req.kwargs))
    app = tiny.App()
    r1, r2, r3, r4 = (tiny.Router() for x in range(4))
    r1.route("/{r1}/txt")(handler)
    r2.route("/{r2}/")(handler)
    r3.route("/{r3}")(handler)
    r4.route("/four")(handler)
    app.mount("/r1a/{base}/", r1)
    app.mount("/r1b/{r1}/", r1)
    app.mount("/r2/{base}/", r2)
    app.mount("/r2a/{base}", r2)
    app.mount("/r3/{base}/", r3)
    app.mount("/r4/{base}/", r4)
    app.mount("/r2b", r2)

    self.assertProducesResponse(app, "/r1a/x1/x2/txt", 200, "[base]=[x1] [r1]=[x2]", "basic")
    self.assertProducesResponse(app, "/r1b/x1/x2/txt", 200, "[r1]=[x2]", "mounted entry overrides")
    self.assertProducesResponse(app, "/r2/x1/x2/", 200, "[base]=[x1] [r2]=[x2]", "with trailing slash")
    self.assertProducesResponse(app, "/r2/x1/x2", 404, msg="called without trailing slash")
    self.assertProducesResponse(app, "/r3/x1/x2", 200, "[base]=[x1] [r3]=[x2]", "trailing slash on mounted")
    self.assertProducesResponse(app, "/r3/x1/x2/", 404, msg="trailing slash inappropraite")
    self.assertProducesResponse(app, "/r2a/x1/x2/", 200, "[base]=[x1] [r2]=[x2]", "base trailing slash implicit")
    self.assertProducesResponse(app, "/r4/x1/four", 200, "[base]=[x1]", "no kw on mounted")
    self.assertProducesResponse(app, "/r4/x1/four", 200, "[base]=[x1]", "no kw on mounted")
    self.assertProducesResponse(app, "/r2b/x1/", 200, "[r2]=[x1]", "no kw on base")

class RequestTest(base.TinyAppTestBase):
  def test_kwargs(self):
    app = tiny.App()
    @app.route("/api/{ver:v\d+}/get/{kind}/{id:\d+}/")
    def _(req, resp):
      raise NotImplementedError
    pass

# TODO: Test
#  * route: test regex compile exceptoin on route (not use)
#
#  * Request supplies:
#    * kwargs
#    * fieldstores
#    * headers

# TODO: response stuff, encoding, file transfers, custom resonses, etc.

class HandlingTest(base.TinyAppTestBase):
  def test_http_error(self):
    app = tiny.App()
    @app.route("/err")
    def _(i,o):
      raise tiny.HttpError(567)
    self.assertProducesResponse(app, "/err", 567)

  def test_classic_exception(self):
    app = tiny.App()
    app.tracebacks_to_stderr=False
    @app.route("/err")
    def _(i,o):
      raise ValueError("Boom!")
    self.assertProducesResponse(app, "/err", 500)

  def test_classic_traceback_display(self):
    SENTINEL = "kTEHKdaRnkRSTf3upf4M"
    app = tiny.App()
    app.tracebacks_to_stderr=False
    @app.route("/err")
    def _(i,o):
      raise ValueError(SENTINEL)

    app.tracebacks_to_http = False
    resp = base.Request("/err").get_response(app)
    self.assertNotIn(SENTINEL, resp.output_str())

    app.tracebacks_to_http = True
    resp = base.Request("/err").get_response(app)
    self.assertIn(SENTINEL, resp.output_str())
