"""Types used by tinyaf."""

import typing
from typing import Callable, Any, TypeVar, Optional, TypedDict



# _WSGI_KEYS = {
#     'REQUEST_METHOD': str,
#     'SCRIPT_NAME': str,
#     'PATH_INFO': str,
#     'QUERY_STRING': str,
#     'CONTENT_TYPE': str,
#     'CONTENT_LENGTH': str,
#     'SERVER_NAME': str,
#     'SERVER_PORT': str,
#     'SERVER_PROTOCOL': str,
#     'wsgi.version': tuple[int, int],
#     'wsgi.url_scheme': str,
#     'wsgi.input': typing.IO[Any],
#     'wsgi.errors': typing.IO[Any],
#     'wsgi.multithread': bool,
#     'wsgi.multiprocess': bool,
#     'wsgi.run_once': bool
# }

# class Environ(dict):
#     def __new__(cls,*args, **kwargs):
#       inst = super(Environ, cls).__new__(*args, **kwargs)
#       for k,t in _WSGI_KEYS:
#          setattr(
#     def _lookup_str(self, key:str) -> str:
#        return self.get(key, None)



# Environ = TypedDict("Environ", dict(_WSGI_KEYS))
