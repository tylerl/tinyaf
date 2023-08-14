from tests import helper
import tinyaf
import typing as t


expect_response = helper.assert_produces_response
basic_handler = helper.basic_handler

def test_url_vars():
    app = tinyaf.App()
    @app.route(r"/api/<ver:v\d+>/get/<kind>/<id:\d+>")
    def _(req:tinyaf.Request, resp):
        return tinyaf.JsonResponse(req.vars)

    expect_response(app, "/api/v2/get/fish/37", 200, dict(id='37', kind='fish', ver='v2'))
    expect_response(app, "/api/v/get/fish/37", 404)
    expect_response(app, "/api/v2/get/fish/bad", 404)


# def test_route_vars(self):
#     app = tinyaf.App()

#     @app.route(r"/api/<ver:v\d+>/get/<kind>/<id:\d+>", vars={'hello': 1, 'kind': 'other'})
#     def _(req, resp):
#         return tinyaf.JsonResponse(req.vars)

#     self.assertProducesJson(app, "/api/v2/get/fish/37",
#                             dict(hello=1, id='37', kind='other', ver='v2'))

# def test_brace_regex(self):

#     app = tinyaf.App()
#     @app.route(r"/foo/<bar:\d{3}-\d{4}>/baz")
#     def _(req, resp):
#         return tinyaf.JsonResponse(req.vars)

#     self.assertProducesJson(app, "/foo/867-5309/baz", {"bar": "867-5309"})


# def test_fields_formurl(self):
#     app = tinyaf.App()
#     app.route("/", handler=lambda req, _: tinyaf.JsonResponse(req.fields))
#     env = dict(CONTENT_TYPE="application/x-www-form-urlencoded")
#     data = "foo=bar&baz=2"
#     self.assertProducesJson(app, "/", dict(foo="bar", baz="2"), env=env, postdata=data)

# def test_fields_formdata(self):
#     app = tinyaf.App()
#     app.route("/", handler=lambda req, _: tinyaf.JsonResponse(req.fields))
#     env = dict(CONTENT_TYPE="multipart/form-data; boundary=XyZ")
#     data = textwrap.dedent("""
#         --XyZ
#         content-disposition: form-data; name="hello"

#         world
#         --XyZ
#         content-disposition: form-data; name="foo"

#         42
#         --XyZ--
#         """)
#     self.assertProducesJson(app, "/", dict(hello='world', foo='42'), env=env, postdata=data)

# def test_fields_querystring(self):
#     app = tinyaf.App()
#     app.route("/", handler=lambda req, _: tinyaf.JsonResponse(req.fields))
#     env = dict(QUERY_STRING='hello=world&foo=42')
#     self.assertProducesJson(app, "/", dict(hello='world', foo='42'), env=env)

# def test_headers(self):
#     app = tinyaf.App()
#     app.route("/", handler=lambda req, _: tinyaf.JsonResponse(dict(req.headers)))
#     o = { "Accept-Language": "en-US", "Connection": "close" }
#     env = dict(HTTP_ACCEPT_LANGUAGE='en-US', HTTP_CONNECTION='close')
#     self.assertProducesJson(app, "/", obj=o, fuzzy=True, env=env)

# def test_reqvars(self):
#     app = tinyaf.App()
#     app.route(r"^.*",
#         handler=lambda req, _: tinyaf.JsonResponse(dict(method=req.method, path=req.path)))
#     self.assertProducesJson(app, "/foo/bar?baz", dict(method="GET", path="/foo/bar"))
