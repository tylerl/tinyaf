from __future__ import absolute_import

import textwrap

from . import base
import tiny


class RouteTest(base.TinyAppTestBase):
  def test_exact_route(self):
    """Verify non-regex routes aren't regex or prefix matched."""
    app = tiny.App()
    app.route("/", handler=lambda req,resp: "A")
    app.route("/fo.", handler=lambda req,resp: "B")
    app.route("/bar", handler=lambda req,resp: "X")

    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/fo.", 200, "B")
    self.assertProducesResponse(app, "/foo", 404)
    self.assertProducesResponse(app, "/bar/foo", 404)
    self.assertProducesResponse(app, "/foo/bar", 404)

  def test_fuzzy_route(self):
    """Test non-regex pattern matching."""
    app = tiny.App()
    app.route("/", handler=lambda req,resp: "A")
    app.route("/*/bar", handler=lambda req,resp: "B")
    app.route("/foo/*/baz", handler=lambda req,resp: "C")

    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/foo/bar", 200, "B")
    self.assertProducesResponse(app, "/far/bar", 200, "B")
    self.assertProducesResponse(app, "/foo/far/baz", 200, "C")
    self.assertProducesResponse(app, "//bar", 404)
    self.assertProducesResponse(app, "/foo/far", 404)

  def test_regex_route(self):
    """Verify regex routes are regex matched."""
    app = tiny.App()
    app.route(r"^/$", handler=lambda req,resp: "A")
    app.route(r"^/fo.$", handler=lambda req,resp: "B")
    app.route(r"^/bar", handler=lambda req,resp: "pfx")

    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/foo", 200, "B")
    self.assertProducesResponse(app, "/bar/foo", 200, "pfx")
    self.assertProducesResponse(app, "/foo/bar", 404)

  def test_error_handler(self):
    """Verify custom error handlers get called, even on implicit (404) Errors."""
    app = tiny.App()
    app.route(r"/", handler=lambda req,resp: "OK")
    app.errorhandler(404, handler=lambda req,resp: "NOT OK")
    app.errorhandler(567, handler=lambda req,resp: "OTHER")
    @app.route("/other")
    def _(i,o):
      raise tiny.HttpError(567)

    self.assertProducesResponse(app, "/", 200, "OK")
    self.assertProducesResponse(app, "/foo", 404, "NOT OK")
    self.assertProducesResponse(app, "/other", 567, "OTHER")

  def test_method_miss(self):
    """Verify 405s error generated for method not found."""
    app = tiny.App()
    app.route(r"/", methods=['GET'], handler=lambda req,resp: "/@G")
    app.route(r"/", methods=['POST'], handler=lambda req,resp: "/@P")
    app.route(r"/gp", methods=['GET', 'POST'], handler=lambda req,resp: "/gp@GP")
    app.route(r"/g", methods=['GET'], handler=lambda req,resp: "/g@G")
    app.route(r"/p", methods=['POST'], handler=lambda req,resp: "/p@P")
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
    r.route("/", handler=lambda req,resp: "A")
    r.route(r"^/pf.x$", handler=lambda req,resp: "B")
    r.errorhandler(404, handler=lambda req,resp: "Z")
    app = tiny.App(router=r)
    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/pf0x", 200, "B")
    self.assertProducesResponse(app, "/nofind", 404, "Z")
    # and then complicate by adding another route and validating old ones
    r.route("/bar", handler=lambda req,resp: "C")
    self.assertProducesResponse(app, "/", 200, "A")
    self.assertProducesResponse(app, "/pf0x", 200, "B")
    self.assertProducesResponse(app, "/nofind", 404, "Z")
    self.assertProducesResponse(app, "/bar", 200, "C")


class RequestTest(base.TinyAppTestBase):
  def test_kwargs(self):
    app = tiny.App()
    @app.route("/api/{ver:v\d+}/get/{kind}/{id:\d+}")  # pylint: disable=W1401
    def _(req, resp):
      return tiny.JsonResponse(req.kwargs)
    self.assertProducesJson(app, "/api/v2/get/fish/37", dict(id='37', kind='fish', ver='v2'))

  def test_fields_formurl(self):
    app = tiny.App()
    app.route("/", handler=lambda req, _: tiny.JsonResponse(req.fields))
    env = dict(CONTENT_TYPE="application/x-www-form-urlencoded")
    data = "foo=bar&baz=2"
    self.assertProducesJson(app, "/", dict(foo="bar",baz="2"), env=env, postdata=data)

  def test_fields_formdata(self):
    app = tiny.App()
    app.route("/", handler=lambda req, _: tiny.JsonResponse(req.fields))
    env = dict(CONTENT_TYPE="multipart/form-data; boundary=XyZ")
    data = textwrap.dedent("""
      --XyZ
      content-disposition: form-data; name="hello"

      world
      --XyZ
      content-disposition: form-data; name="foo"

      42
      --XyZ--
    """)
    self.assertProducesJson(app, "/", dict(hello='world',foo='42'), env=env, postdata=data)

  def test_fields_querystring(self):
    app = tiny.App()
    app.route("/", handler=lambda req, _: tiny.JsonResponse(req.fields))
    env=dict(QUERY_STRING='hello=world&foo=42')
    self.assertProducesJson(app, "/", dict(hello='world',foo='42'), env=env)

  def test_headers(self):
    app = tiny.App()
    app.route("/", handler=lambda req, _: tiny.JsonResponse(dict(req.headers)))
    self.assertProducesJson(app, "/", obj={"Accept-Language":"en-US", "Connection": "close"},
        fuzzy=True, env=dict(HTTP_ACCEPT_LANGUAGE='en-US', HTTP_CONNECTION='close'))

  def test_reqvars(self):
    app = tiny.App()
    app.route(r"^.*", handler=lambda req, _: tiny.JsonResponse(dict(method=req.method, path=req.path)))
    self.assertProducesJson(app, "/foo/bar?baz", dict(method="GET",path="/foo/bar"))


class ResponseTest(base.TinyAppTestBase):

  def test_write(self):
    app = tiny.App()
    @app.route("/")
    def _(_resp, _req):
      resp = tiny.Response()
      resp.write("hello".encode('utf-8'))
      resp.write(" world".encode('utf-8'))
      return resp
    self.assertProducesResponse(app, "/", 200, "hello world")

  def test_contents_array(self):
    app = tiny.App()
    @app.route("/")
    def _(_resp, _req):
      return tiny.Response(content=["hello world".encode("utf-8")])
    self.assertProducesResponse(app, "/", 200, "hello world")

  def test_contents_iter(self):
    app = tiny.App()
    @app.route("/")
    def _(_resp, _req):
      return tiny.Response(content=(x.encode('utf-8') for x in "hello again world".split()))
    self.assertProducesResponse(app, "/", 200, "helloagainworld")

  def test_default_headers(self):
    app = tiny.App()
    @app.route("/")
    def _(req, resp):
      if 'ct' in req:
        resp.headers['content-type'] = req['ct']
      return "OK"
    r_def = base.Request("/").get_response(app)
    r_alt = base.Request("/?ct=text/poem").get_response(app)
    self.assertResponse(r_def, 200, "OK")
    self.assertResponse(r_alt, 200, "OK")
    self.assertEqual("text/html; charset=utf-8", r_def.headers_dict['content-type'])
    self.assertEqual("text/poem", r_alt.headers_dict['content-type'])

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

class RequestForwardTest(base.TinyAppTestBase):
  def test_wsgi_forward(self):
    app1 = tiny.App()
    app2 = tiny.App()

    @app1.route("/")
    def _1(req, resp):
      resp = req.forward_wsgi(app2)
      resp.headers["App1"] = "OK"
      return resp

    @app2.route("/")
    def _2(req, resp):
      resp.headers["App2"] = "OK"
      return "Hello App 2"

    resp = base.Request("/").get_response(app1)
    self.assertResponse(resp, 200, "Hello App 2")
    self.assertDictFuzzy({"App1":"OK", "App2":"OK"}, resp.headers_dict)

  def test_app_forward(self):
    app1 = tiny.App()
    app2 = tiny.App()

    @app1.route("/")
    def _1(req, resp):
      resp = req.forward(app2)
      resp.headers["App1"] = "OK"
      return resp

    @app2.route("/")
    def _2(req, resp):
      resp.headers["App2"] = "OK"
      return "Hello App 2"

    resp = base.Request("/").get_response(app1)
    self.assertResponse(resp, 200, "Hello App 2")
    self.assertDictFuzzy({"App1":"OK", "App2":"OK"}, resp.headers_dict)


# TODO: json response, file response, encoding


