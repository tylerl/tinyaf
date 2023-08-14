# import typing as t
# import pytest
# import inspect
# from _pytest.assertion import util as _pytest_util
# from dataclasses import dataclass

# OP_REVERSE = {"==": '==', '!=': '!=', 'in': 'contains'}
# OP_NAMES = {
#     '==': 'eq',
#     '!=': 'ne',
#     '<': 'lt',
#     '>': 'gt',
#     'in': 'in',
#     'contains': 'contains',
# }

# def _maybe_call(obj:object, fnName:str, *args, **kwargs):
#     fn = getattr(obj, fnName, None)
#     if callable(fn):
#         return fn(*args, **kwargs)
#     return None

# def pytest_assertrepr_compare(config: pytest.Config, op: str, left, right):
#     if op in OP_NAMES:
#         if rtn := _maybe_call(left, f'_repr_{OP_NAMES[op]}_', right):
#             return rtn
#     if rtn := _maybe_call(left, f'_repr_compare_', op, right):
#         return rtn
#     if revop := OP_REVERSE.get(op):
#         if revop in OP_NAMES:
#             if rtn := _maybe_call(right, f'_repr_{OP_NAMES[revop]}_', left):
#                 return rtn
#         if rtn := _maybe_call(right, f'_repr_compare_', revop, left):
#             return rtn