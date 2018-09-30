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

    # TODO: test deep recursion (10-ish?)
    # TODO: test infinite recursion (valueerror -> http500)


# TODO: Test
#  * positional route arguments
#  * kw route arguments
#  * positional bind-mounted arguments (top-level only)
#  * kw bind-mounted arguments (all levels)

# TODO: Test
#  * Request supplies:
#    * args, kwargs
#    * fieldstores
#    * headers

# TODO: response stuff, encoding, file transfers, custom resonses, etc.