# Tiny App Framework

TinyAF is an exceptionally small Web Application Framework for Python WSGI.

This framework has no dependencies outside the standard library, and consists
of only about 300 lines of code.

The intended use case is building minimal, self-contained web application
servers. The framework is designed to make it reasonable to simply paste the
contents of tiny.py into your code, and ship a single file as your entire
application.

Because of the copy-paste deployment is the primary expected use case, tiny.py
is highly optimized for code size, such that each potential feature has been
carefully balanced against the space required to code that feature. At the same
time, the design is intended to capture all the most important web app
expectations, so that you don't miss the features you're missing from more
comprehensive frameworks like Flask, Django, or Bottle.