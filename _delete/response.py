"""TinyAF Request types."""
import contextlib
import http
import json
import types
import typing as t
from dataclasses import InitVar, dataclass, field
from wsgiref.headers import Headers

from ..tinyaf.core import HttpError, Request, Response, StringResponse

__all__ = ["Response", "StringResponse", "JsonResponse"]

_O = t.Optional
_T = t.TypeVar("_T")
_WsgiHeaders: t.TypeAlias = list[tuple[str, str]]
_AnyHeaders: t.TypeAlias = dict[str, str] | _WsgiHeaders | Headers
_ExecInfo = tuple[type[BaseException], BaseException, types.TracebackType]
_FinalizeArgs: t.TypeAlias = (tuple[str, _WsgiHeaders] |
                              tuple[str, _WsgiHeaders, None | _ExecInfo])

_ContentT = t.TypeVar("_ContentT")

# pylint: disable=unused-argument
