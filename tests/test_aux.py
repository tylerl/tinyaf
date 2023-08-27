import tinyaf.util
import pytest


@pytest.mark.parametrize(
    ("src", "expect_val", "expect_params"), [
        # without quotes
        ("text/html;charset=utf8", "text/html", {'charset': 'utf8'}),
        # with quoted val
        ('text/html;charset="utf8"', "text/html", {'charset': 'utf8'}),

        # the rest adapted from werkzeug tests
        ("v;a=b;c=d;", "v", {"a": "b", "c": "d"}),
        ("v;  ; a=b ; ", "v", {"a": "b"}),
        ("v;a", "v", {}),
        ("v;a=", "v", {}),
        ("v;=b", "v", {}),
        ('v;a="b"', "v", {"a": "b"}),
        ('v;a="\';\'";b="µ";', "v", {"a": "';'", "b": "µ"}),
        ('v;a="b c"', "v", {"a": "b c"}),
        # HTTP headers use \" for internal "
        ('v;a="b\\"c";d=e', "v", {"a": 'b"c', "d": "e"}),
        # HTTP headers use \\ for internal \
        ('v;a="c:\\\\"', "v", {"a": "c:\\"}),
        # Invalid trailing slash in quoted part is left as-is.
        ('v;a="c:\\"', "v", {"a": "c:\\"}),
        ('v;a="b\\\\\\"c"', "v", {"a": 'b\\"c'}),
        # multipart form data uses %22 for internal "
        ('v;a="b%22c"', "v", {"a": 'b"c'}),
        ('v;a="🐍.txt"', "v", {"a": "🐍.txt"}),
    ]
)
def test_parse_header_options(src, expect_val, expect_params):
    assert tinyaf.util.parse_header_options(src) == (expect_val, expect_params)


def test_parse_header_complex():
    s = 'foo;a=x;b="y";c="x;y"'
    escaped = s.replace('\\', '\\\\').replace('"', '\\"')
    test_parse_header_options(s, "foo", {'a': 'x', 'b': 'y', 'c': 'x;y'})
    test_parse_header_options(f'bar;x="{escaped}"', "bar", {'x': s})  # tests full embedding
