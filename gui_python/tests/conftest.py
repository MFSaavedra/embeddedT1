"""Make `import protocol` etc. work when running `pytest gui_python/tests`."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
