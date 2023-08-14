from tests.util import wsgi
from tests import _config

import typing as t
import tinyaf
from dataclasses import dataclass
from _pytest.assertion import util as _pytest_util


@dataclass(slots=True)
class _Fault:
    key: str
    want: t.Any
    got: t.Any

    def __str__(self):
        return f"{self.key}: expected={self.want!r}, got={self.got!r}"


def basic_handler(content: t.Any, response_type=tinyaf.Response):
    def handler(request: tinyaf.Request, response: response_type):
        return content
    return handler


def assert_response(resp: wsgi.Response,
                    code: int,
                    content: None | str | bytes | dict | list = None,
                    headers: None | dict[str, str] = None,
                    ignore_extra_headers=True,
                    ):
    __tracebackhide__ = True
    faults = []

    if code != resp.code:
        faults.append(_Fault("Response.code", code, resp.code))

    if content is not None:
        match content:
            case bytes():
                resp_content = resp.output_bytes()
            case str():
                resp_content = resp.output_str()
            case dict() | list():
                resp_content = resp.output_json()
            case _:
                raise ValueError(f"content is unknown type: ({type(content)})")
        if content != resp_content:
            faults.append(_Fault("Response.content", content, resp_content))

    if headers or not ignore_extra_headers:
        for k, want, got in _headers_zip(
                headers or {}, resp.headers_normalized, not ignore_extra_headers):
            if want == got or _header_normalize(want) == _header_normalize(got):
                continue
            faults.append(_Fault(f"Response.header[{k}]", want, got))

    if faults:
        if len(faults) == 1 and not _config.verbose:
            msg = str(faults[0])
        else:
            details = [repr(resp), *[f">> {f}" for f in faults]]
            if _config.verbose:
                details.append(">-----RESPONSE DUMP-----")
                details.extend(
                    f">|{line}" for line in resp.dump().splitlines())
            msg = "\n".join(details)
        raise AssertionError(_pytest_util.format_explanation(msg))


def assert_produces_response(
        app: wsgi.WSGIApplication,
        url: str,
        code: int,
        content: str | bytes | dict | list | None = None,
        headers: None | dict[str, str] = None,
        **argv):
    __tracebackhide__ = True
    got = wsgi.Request(url, **argv).get_response(app)
    assert_response(got, code, content, headers)


def _headers_zip(want: dict[str, str], got: dict[str, str], keep_missing=False):
    """Yields (key, want, got) ignoring case on keys."""
    want = {k.lower():v for k,v in want.items()}
    got = {k.lower():v for k,v in got.items()}
    for k, v_want in want.items():
        v_got = got.get(k)
        yield k, v_want, v_got
    if keep_missing:
        for k, v_got in got.items():
            if k not in want:
                yield k, None, v_got


def _header_normalize(val: str | None):
    if val is None:
        return None
    return ",".join(sorted(s.strip() for s in val.split(",")))
