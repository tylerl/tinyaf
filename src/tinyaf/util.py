import dataclasses
import re
import inspect
import typing as t
import itertools
import codecs

_T = t.TypeVar("_T")

# TODO: Remove this disable and fill in docstrings
# pylint: disable=missing-class-docstring, disable=missing-function-docstring

# def factory(fn: t.Callable[[],_T]) -> _T:
#     return dataclasses.field(default_factory=fn)


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


def _quoted_split(delim: str, line: str, trim=True) -> t.Iterable[str]:
    """Splits a string along delim, allowing for that string to be quoted."""
    regex = r'(?:[^{0}"\\]+|"(?:[^"\\]|\\\\|\\")*")+'.format(delim)
    if m := re.findall(regex, line):
        if trim:
            return (s.strip() for s in m)
        return m
    return ()


def _eq_items(l: list[str]):
    for k, v in (s.split("=", 1) for s in l if "=" in s):
        k, v = k.strip(), v.strip()
        print(f">>> k=[{k}] v=[{v}]")
        if len(v) > 1 and v[0] == '"' and v[-1] == '"':
            yield k.lower(), v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        else:
            yield k.lower(), v


class _tok:
    def __init__(self, delim:str):
        e_delim = re.escape(delim)
        self.disallow = e_delim
        self.re_text = e_delim

class _quoted_tok(_tok):
    def __init__(self, begin: str, end: str):
        e_begin, e_end = re.escape(begin), re.escape(end)
        self.disallow = e_begin
        self.re_text = rf'{e_begin}(?:[^{e_end}\\]|\\.)*{e_end}'

class _tokenizer:
    def __init__(self, *tokens: _tok):
        other = rf'[^{"".join(x.disallow for x in tokens)}\\]+'
        pats = [t.re_text for t in tokens] + [other]
        self.re_text = rf"(?:{  '|'.join(rf'(?:{p})' for p in pats)  })"
        self.re_comp = re.compile(self.re_text)

    def tokenize(self, str):
        tokens = (x.strip() for x in self.re_comp.findall(str))
        return (t for t in tokens if t)

QUOTED_TEXT = _quoted_tok('"', '"')  # quote-enclosed string with escapes
COMMENT_TEXT = _quoted_tok('(', ')')  # parens-enclosed string with escapes
COMMA_SEP = _tokenizer(QUOTED_TEXT, COMMENT_TEXT, _tok(","))
KVP_SEP = _tokenizer(QUOTED_TEXT, COMMENT_TEXT, _tok("="), _tok(";"))

def _list_split(delim:str, l:list[str]):
    return (list(v) for k,v in itertools.groupby(l,lambda x:x!=delim) if k)

def parse_header(val:str, simplified=True):
    """Parse a header like content-type -> "somestr; k1=v1;k2=v2". """
    tokens = list(KVP_SEP.tokenize(val))
    alone = []
    kvp = dict()
    for sets in _list_split(";", tokens):
        match sets:
            case [k, "=", v]:
                if len(v) > 1 and v[0]=='"' and v[-1]=='"':
                    v = v[1:-1].replace('\\"', '"')
                if simplified:
                    kvp[k] = v
                else:
                    l = kvp.setdefault(k,[])
                    l.append(v)
            case [val]:
                alone.append(val)
            case unknown:
                alone.extend(unknown)
    first, *others = alone or [""]
    return ( first, kvp, others )
