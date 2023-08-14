from tests import helper
import tinyaf
import typing as t

expect_response = helper.assert_produces_response
basic_handler = helper.basic_handler


def test_basic():
    app = tinyaf.App()
    @app.route("/")
    def handler(request: tinyaf.Request, response: tinyaf.Response):
        return "hello"
    expect_response(app, "/", 200, "hello")
