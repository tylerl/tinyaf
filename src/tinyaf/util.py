import dataclasses
import re
import inspect
import typing as t
import itertools
import codecs

from urllib.request import parse_http_list as _parse_list_header

_T = t.TypeVar("_T")

# TODO: Remove this disable and fill in docstrings
# pylint: disable=missing-class-docstring, disable=missing-function-docstring

def path_to_pattern(val: str) -> re.Pattern[str]:
    """Encode non-regex patterns as regex."""
    if val[0] == '^':
        return re.compile(val)  # indicates raw regex

    def esc(s):
        return re.escape(re.sub(r"//+", "/", "/" + s))

    def parts(val):
        i = 0  # pattern below is "*" or "<identifier>" or "<identifier:regex>"
        # complicated because escaping > is allowed ("<ident:foo\>bar>")
        yield "^"
        for m in re.finditer(r'(<([a-zA-Z0-9\.]+)(?::((?:\\.|[^>])*))?>)|(\*)', val):
            if m.start() > i:
                yield esc(val[i:m.start()])
            if m.group() == "*":
                yield r"[^/]+"
            else:
                yield "(?P<%s>%s)" % (m.groups()[1], m.groups()[2] or r'[^/]+')
            i = m.end()
        if i < len(val):
            yield esc(val[i:])
        yield "$"
    return re.compile("".join(parts(val)))

def type_from_callable(func, index):
    try:
        params = inspect.signature(func).parameters
        param_type = list(params.values())[index].annotation
        if param_type != inspect.Parameter.empty:
            return param_type
    except (TypeError, IndexError):
        pass
    return None

# XXX: HERE
# TODO: maybe do better header manipulation
_KVP_RE = re.compile(
    r"""\s*;\s*(?:                        # prefix by delim
        ([^"=\s;]+) =                     # key (group 1)
        ([^"=\s;]+ | "(?:\\\\|\\"|.)*?" ) # val (group 2)
    )?""", re.VERBOSE)

def _unquote(val:str, unescape=False):
    if len(val)>=2 and '"' == val[0] == val[-1]:
        if unescape:
            return val[1:-1].replace("\\\\", "\\").replace('\\"', '"').replace("%22", '"')
    return val

def _header_kvp(val:str):
    for k,v in _KVP_RE.findall(f";{val}"):
        k, v = k.strip(), _unquote(v.strip(), True)
        if k:
            yield k,v

def parse_header_list(val:str):
    items = (_unquote(x.strip(), False) for x in _parse_list_header(val))
    return [x for x in items if x]

def parse_header_dict(val:str):
    return dict(_header_kvp(val))

def parse_header_options(val:str):
    first, _, rest = val.partition(';')
    return first.strip(), parse_header_dict(rest)

def parse_multipart():
    pass`