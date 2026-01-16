"""django-dirtyfields library for tracking dirty fields on a Model instance."""

__all__ = ["DirtyFieldsMixin"]
__version__ = "2.0.0"

from dirtyfields.dirtyfields import DirtyFieldsMixin

VERSION = tuple(map(int, __version__.split(".")[0:3]))
