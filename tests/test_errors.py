import tinyaf
import pytest


class _CustomError(Exception):
    """Some generic error type."""


def test_basic_httperror():
    CODE = 417
    try:
        raise tinyaf.HttpError(CODE)
    except tinyaf.HttpError as ex:
        err = ex
    assert err.code == CODE
    assert isinstance(err, tinyaf.HttpError)
    assert err.has_cause() == False, "Without a base error there shouldn't be a cause."
    assert list(err.causes()) == [], "Causes should be empty."


def test_raise_from():
    CODE = 417
    valError = ValueError("sample value error")
    try:
        raise tinyaf.HttpError(CODE) from valError
    except tinyaf.HttpError as ex:
        err = ex
    assert isinstance(err, tinyaf.HttpError)
    assert err.code == CODE
    assert err.has_cause(), "Error raised from another should have a cause."
    assert list(err.causes()) == [
        valError], "Cause should contain only the FROM exception."


@pytest.mark.parametrize("code,short,args,kwargs", [
    (500, None, [], dict()),
    (417, None, [417], dict()),
    (417, "hello", [417, "hello"], dict()),
    (417, "hello", [417], dict(short="hello")),
    (417, "hello", [], dict(code=417, short="hello")),
    (500, "hello", [], dict(short="hello"))])
def test_raise_wrapped(code, short, args, kwargs):
    valError = ValueError("sample value error")
    try:
        with tinyaf.HttpError.wrap_exceptions(*args, **kwargs):
            raise valError
    except tinyaf.HttpError as ex:
        err = ex
    assert isinstance(err, tinyaf.HttpError)
    assert err.has_cause()
    assert list(err.causes()) == [valError]
    assert err.code == code
    assert err.short == short


def test_nested_error():
    inner = _CustomError("sample value error")
    outer = ValueError("sample value error")
    try:
        with tinyaf.HttpError.wrap_exceptions():
            try:
                raise inner
            except _CustomError as inner_ex:
                raise outer from inner
    except tinyaf.HttpError as ex:
        err = ex
    assert err.code == 500
    assert err.has_cause()
    assert list(err.causes()) == [outer, inner]
