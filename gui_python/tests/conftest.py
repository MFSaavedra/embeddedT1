"""@file conftest.py
@brief Make `import protocol` etc. work when running `pytest gui_python/tests`.

Prepends gui_python/ to sys.path so the tests import the modules exactly as the
application does.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
