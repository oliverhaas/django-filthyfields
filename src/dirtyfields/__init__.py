"""django-filthyfields library for tracking dirty fields on a Model instance."""

from importlib.metadata import version

__all__ = ["DirtyFieldsMixin"]
__version__ = version("django-filthyfields")

from dirtyfields.dirtyfields import DirtyFieldsMixin
