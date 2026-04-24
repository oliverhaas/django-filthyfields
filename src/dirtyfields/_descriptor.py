# cython: freethreading_compatible=True
# ruff: noqa: ERA001
"""Diff descriptor for dirty-field tracking.

This module is written in Cython *pure-Python mode* — a regular ``.py`` file
with ``@cython.cclass`` and ``@cython.cfunc`` decorators.

* Runs as a plain Python class when not compiled (no Cython needed at runtime
  — there's a stub for that case).
* When compiled with ``cythonize -i``, becomes a C extension type whose
  ``__get__`` / ``__set__`` are the ``tp_descr_get`` / ``tp_descr_set`` slots.
  CPython's attribute machinery calls them directly, no Python frame, and
  the typed instance attributes are C struct members instead of ``__dict__``
  entries.

Uses *composition*, not inheritance, around Django's ``DeferredAttribute``:
we hold one as a member and delegate to it for the deferred-load fallback
on ``__get__``. Inheriting from a Python class from a ``cdef class`` is
awkward and loses half the point.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

try:
    import cython  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - cython not installed at runtime (pure-Python path)
    # Minimal stub so the module runs without the cython package installed.
    # When compiled, cython is always available and this branch is skipped.
    class _CythonStub:
        bint = bool

        @staticmethod
        def cclass(klass: Any) -> Any:
            return klass

        @staticmethod
        def cfunc(fn: Any) -> Any:
            return fn

        @staticmethod
        def inline(fn: Any) -> Any:
            return fn

    cython = _CythonStub()  # ty: ignore[invalid-assignment]

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db.models.expressions import BaseExpression, Combinable

if TYPE_CHECKING:
    from django.db import models

_IMMUTABLE_TYPES = frozenset(
    (
        int,
        float,
        complex,
        str,
        bool,
        bytes,
        range,
        Decimal,
        UUID,
        date,
        datetime,
        time,
        timedelta,
    ),
)

# Types whose values can be mutated in place without going through __set__.
# Used for TRACK_MUTATIONS snapshotting in __get__.
_MUTABLE_TYPES = frozenset((dict, list, set, bytearray))


def _normalize_value(value: Any) -> Any:
    """Normalize a field value for storage in the diff dict."""
    if value is None or type(value) in _IMMUTABLE_TYPES:
        return value
    if isinstance(value, File):
        return value.name
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, dict):
        if all(type(v) in _IMMUTABLE_TYPES or v is None for v in value.values()):
            return value.copy()
        return deepcopy(value)
    if isinstance(value, (list, tuple)):
        if all(type(v) in _IMMUTABLE_TYPES or v is None for v in value):
            return list(value) if isinstance(value, list) else value
        return deepcopy(value)
    return deepcopy(value)


@cython.cclass
class DiffDescriptor:
    """Descriptor that tracks field changes via ``__set__``.

    When compiled, this is a Cython extension type — ``__get__`` / ``__set__``
    are C slot functions; the attributes below are C struct members. When not
    compiled, it's a plain Python class with the same semantics.
    """

    _deferred_attr: Any
    _field: Any
    _attname: str
    _field_name: str
    _is_relation: cython.bint
    _track_mutations: cython.bint

    def __init__(
        self,
        field: models.Field[Any, Any],
        deferred_attr: Any,
        track_mutations: bool = False,
    ) -> None:
        self._field = field
        self._deferred_attr = deferred_attr
        self._attname = field.attname
        self._field_name = field.name
        self._is_relation = field.remote_field is not None
        self._track_mutations = track_mutations

    @cython.cfunc  # type: ignore[untyped-decorator]
    @cython.inline  # type: ignore[untyped-decorator]
    def _values_equal(self, val1: Any, val2: Any) -> cython.bint:
        """Compare values with field-level to_python fallback for type coercion."""
        if type(val1) is type(val2):
            return val1 == val2
        try:
            return self._field.to_python(val1) == self._field.to_python(val2)
        except (ValidationError, TypeError, ValueError):  # fmt: skip
            return val1 == val2

    def __get__(self, instance: Any, cls: Any) -> Any:
        if instance is None:
            return self
        d = instance.__dict__
        try:
            value = d[self._attname]
        except KeyError:
            return self._deferred_attr.__get__(instance, cls)

        # TRACK_MUTATIONS: deepcopy the value on first read so in-place mutations
        # (e.g. obj.json_field["k"] = "v") are still detectable at get_dirty_fields() time.
        if self._track_mutations and type(value) in _MUTABLE_TYPES:
            snap = d.get("_state_mut_snapshot")
            if snap is None:
                snap = {}
                d["_state_mut_snapshot"] = snap
            if self._field_name not in snap:
                snap[self._field_name] = deepcopy(value)
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        if instance is None:
            return

        d = instance.__dict__
        attname = self._attname

        # ORM expressions (F, Func, ...) get resolved at save time, not tracked as edits.
        if isinstance(value, (BaseExpression, Combinable)):
            d[attname] = value
            return

        # Fast path: new instance being populated, or field not yet loaded
        try:
            state = instance._state
            if state.adding or attname not in d:
                d[attname] = value
                return
        except AttributeError:
            d[attname] = value
            return

        # FIELDS_TO_CHECK / FIELDS_TO_CHECK_EXCLUDE (cached per instance)
        field_name = self._field_name
        cache = d.get("_fields_check_cache")
        if cache is None:
            fields_to_check = getattr(instance, "FIELDS_TO_CHECK", None)
            fields_to_exclude = getattr(instance, "FIELDS_TO_CHECK_EXCLUDE", None)
            if fields_to_check is not None and fields_to_exclude is not None:
                raise ValueError(
                    "Cannot use both FIELDS_TO_CHECK and FIELDS_TO_CHECK_EXCLUDE on the same model",
                )
            cache = (fields_to_check, fields_to_exclude)
            d["_fields_check_cache"] = cache

        fields_to_check, fields_to_exclude = cache

        if fields_to_check is not None and field_name not in fields_to_check and attname not in fields_to_check:
            d[attname] = value
            return

        if fields_to_exclude is not None and (field_name in fields_to_exclude or attname in fields_to_exclude):
            d[attname] = value
            return

        old = d[attname]
        d[attname] = value

        if self._values_equal(value, old):
            return

        if self._is_relation and self._field.is_cached(instance):
            self._field.delete_cached_value(instance)

        diff = d.setdefault("_state_diff", {})

        if field_name not in diff:
            diff[field_name] = _normalize_value(old)
            if self._is_relation:
                d.setdefault("_state_diff_rel", set()).add(field_name)
            return

        if self._values_equal(value, diff[field_name]):
            del diff[field_name]
            if self._is_relation:
                rel = d.get("_state_diff_rel")
                if rel:
                    rel.discard(field_name)
