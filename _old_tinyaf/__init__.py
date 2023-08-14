"""TinyAF is an exceptionally small Web Application Framework for Python WSGI.

This framework has no dependencies outside the standard library, and consists
of only about 300 lines of code.

The intended use case is building minimal, self-contained web application
servers. The framework is designed to make it reasonable to simply paste the
contents of tinyaf.py into your code, and ship a single file as your entire
application.

Because of the copy-paste deployment is the primary expected use case, tinyaf.py
is highly optimized for code size, such that each potential feature has been
carefully balanced against the space required to code that feature. At the same
time, the design is intended to capture all the most important web app
expectations, so that you don't miss the features you're missing from more
comprehensive frameworks like Flask, Django, or Bottle.

  This is precisely as minimal an app framework as reasonably tolerable.
"""

from . import _tinyaf_doc
from . import tinyaf as _tinyaf
from .tinyaf import *  # this is redundant, but placates some static analyzers.

import types
import sys

# The __init__ module transparently exports the tinyaf.py module, except that it
# also transparently swaps in the docstrings from _tinyaf_doc.py, so that if you
# import tinyaf (rather than tinyaf.tinyaf) into Python, then you'll end up with
# the full docs in your help text and whatnot.

# Copy all the docstrings from tinyaf_doc into tinyaf
def _copy_docs(a, b):
  for name in (x for x in dir(a) if x[0] != "_"):
    try:
      a1, b1 = getattr(a, name), getattr(b, name)
    except AttributeError:
      continue
    if type(a1) == type(b1) and type(a1) in (types.FunctionType, type):
      if hasattr(a1, '__doc__'):
        try:
          b1.__doc__ = a1.__doc__
        except AttributeError:
          # Py2 doesn't allow assigning docstrings for Classes/types
          pass
      _copy_docs(a1, b1)

# Essentially, `from .tinyaf import *` and set __all__ accordingly.
def _exportall(from_mod, to_mod):
  """Copy the target namespace into the current one."""
  to_mod.__all__ = []
  for k in dir(from_mod):
    if not k.startswith('_'):
      setattr(to_mod, k, getattr(from_mod, k))
      to_mod.__all__.append(k)

_copy_docs(_tinyaf_doc, _tinyaf)
_exportall(_tinyaf, sys.modules[__name__])
# Done with these; remove so that people don't think tinyaf._tinyaf.App is a thing.
del _tinyaf
del _tinyaf_doc
