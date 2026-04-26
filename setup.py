"""Build-time hook that compiles the Cython descriptor extension.

Everything except ``ext_modules`` lives in ``pyproject.toml``. This file exists
only because setuptools doesn't read ``ext_modules`` from ``pyproject.toml``
and we need ``cythonize()`` to process ``_descriptor.py`` into a C extension.
"""

from Cython.Build import cythonize
from setuptools import setup

setup(
    ext_modules=cythonize(
        ["src/filthyfields/_descriptor.py"],
        compiler_directives={"language_level": "3"},
    ),
)
