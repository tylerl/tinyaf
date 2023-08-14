from tests import helper
import tinyaf
import typing as t


expect_response = helper.assert_produces_response
basic_handler = helper.basic_handler

def test_exact_route():
    """Verify non-regex routes aren't regex or prefix matched."""
    app = tinyaf.App()
    app.add_route("/", basic_handler("A"))
    app.add_route("/fo.", basic_handler("B"))
    app.add_route("/bar", basic_handler("X"))

    expect_response(app, "/", 200, "A")
    expect_response(app, "/fo.", 200, "B")
    expect_response(app, "/foo", 404)
    expect_response(app, "/bar/foo", 404)
    expect_response(app, "/foo/bar", 404)


def test_fuzzy_route():
    """Test non-regex pattern matching."""
    app = tinyaf.App()
    app.add_route("/", basic_handler("A"))
    app.add_route("/*/bar", basic_handler("B"))
    app.add_route("/foo/*/baz", basic_handler("C"))

    expect_response(app, "/", 200, "A")
    expect_response(app, "/foo/bar", 200, "B")
    expect_response(app, "/far/bar", 200, "B")
    expect_response(app, "/foo/far/baz", 200, "C")
    expect_response(app, "//bar", 404)
    expect_response(app, "/foo/far", 404)

def test_regex_route():
    """Verify regex routes are regex matched."""
    app = tinyaf.App()
    app.add_route(r"^/$", basic_handler("A"))
    app.add_route(r"^/fo.$", basic_handler("B"))
    app.add_route(r"^/bar", basic_handler("pfx"))

    expect_response(app, "/", 200, "A")
    expect_response(app, "/foo", 200, "B")
    expect_response(app, "/bar/foo", 200, "pfx")
    expect_response(app, "/foo/bar", 404)


def test_error_handler():
    """Verify custom error handlers get called, even on implicit (404) Errors."""
    app = tinyaf.App()
    app.add_route(r"/", basic_handler("OK"))
    app.set_errorhandler(404, basic_handler("NOT OK"))
    app.set_errorhandler(567, basic_handler("OTHER"))

    @app.route("/other")
    def _(i, o):
        raise tinyaf.HttpError(567)

    expect_response(app, "/", 200, "OK")
    expect_response(app, "/foo", 404, "NOT OK")
    expect_response(app, "/other", 567, "OTHER")

def test_method_405s():
    """Verify 405s error generated for method not found."""
    app = tinyaf.App()
    # different handler by method
    app.add_route(r"/", basic_handler("/@G"), methods=['GET'])
    app.add_route(r"/", basic_handler("/@P"), methods=['POST'])
    # allow both methods
    app.add_route(r"/gp", basic_handler("/gp@GP"), methods=['GET', 'POST'])
    # only get
    app.add_route(r"/g", basic_handler("/g@G"), methods=['GET'])
    # only post
    app.add_route(r"/p", basic_handler("/p@P"), methods=['POST'])

    # working routes
    expect_response(app, "/", 200, "/@G", postdata=None)
    expect_response(app, "/", 200, "/@P", postdata='xyz')
    expect_response(app, "/gp", 200, "/gp@GP", postdata=None)
    expect_response(app, "/g", 200, "/g@G", postdata=None)
    expect_response(app, "/p", 200, "/p@P", postdata='xyz')

    # broken routes
    ALLOW_GET = {'Allow': 'GET'}
    ALLOW_POST = {'Allow': 'POST'}
    ALLOW_BOTH = {'Allow': 'GET,POST'}

    expect_response(app, '/g', 405, postdata='xyz', headers=ALLOW_GET)
    expect_response(app, '/p', 405, postdata=None, headers=ALLOW_POST)
    # check multi-method header result
    expect_response(app, '/', 405, method='OPTIONS', headers=ALLOW_BOTH)



# def test_separate_router(self):
# TODO: Not sure whether about mulitple routing in this new version
#     """Verify that external routers can be supplied to an app."""
#     a = tinyaf.App()
#     a.add_route("/", basic_handler("A"))
#     a.add_route(r"^/pf.x$", basic_handler("B"))
#     a.set_errorhandler(404, basic_handler("Z"))

#     app = tinyaf.App()
#     app.add_route("/", a)
#     expect_response(app, "/", 200, "A")
#     expect_response(app, "/pf0x", 200, "B")
#     expect_response(app, "/nofind", 404, "Z")
#     # and then complicate by adding another route and validating old ones
#     a.add_route("/bar", basic_handler("C"))
#     expect_response(app, "/", 200, "A")
#     expect_response(app, "/pf0x", 200, "B")
#     expect_response(app, "/nofind", 404, "Z")
#     expect_response(app, "/bar", 200, "C")
