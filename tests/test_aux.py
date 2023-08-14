import tinyaf.util


def _test_ct(h, want_ct, want_d={}):
    print(f"_test_ct([{h}], [{want_ct}], [{want_d}])")
    ct, d, others = tinyaf.util.parse_header(h)
    assert ct == want_ct
    assert d == want_d
    assert others == []

def _esc(s:str):
    return s.replace(r'\'',r'\\\\').replace(r'"', r'\\"')

def test_parse_header():
    _test_ct("text/html;charset=utf8", "text/html", {'charset': 'utf8'})
    _test_ct('text/html;charset="utf8"', "text/html", {'charset': 'utf8'})
    s = 'foo;a=x;b="y";c="x;y"'
    _test_ct(s, "foo", {'a':'x','b':'y','c':'x;y'})
    #_test_ct(f'bar;x="{_esc(s)}"', "bar", {'x':s})
