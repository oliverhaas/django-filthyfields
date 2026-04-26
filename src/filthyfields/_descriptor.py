# cython: freethreading_compatible=True
# ruff: noqa: ERA001
"""Diff descriptor for dirty-field tracking.

Written in Cython pure-Python mode: runs as plain Python without Cython
installed (via ``_CythonStub``); when compiled, becomes a C extension type
whose ``__get__``/``__set__`` are the ``tp_descr_get``/``tp_descr_set`` slots.

Composition over inheritance around Django's ``DeferredAttribute`` (cdef
classes can't cleanly subclass Python classes).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import PurePath
from typing import TYPE_CHECKING, Any
from uuid import UUID

try:
    import cython  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - pure-Python fallback when cython not installed

    class _CythonStub:
        bint = bool

        @staticmethod
        def cclass(klass: Any) -> Any:
            return klass

        @staticmethod
        def cfunc(fn: Any) -> Any:
            return fn

        @staticmethod
        def ccall(fn: Any) -> Any:
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
        frozenset,
    ),
)

# Isinstance fallback for subclasses of immutable bases (IntEnum, SafeString,
# pathlib subclasses, user-defined subclasses) — safe to share by reference.
_IMMUTABLE_BASES: tuple[type, ...] = (str, int, bytes, PurePath)

# Mutable container types — snapshotted on first __get__ when TRACK_MUTATIONS is on.
_MUTABLE_TYPES = frozenset((dict, list, set, bytearray))


@cython.ccall  # type: ignore[untyped-decorator]
def _normalize_value(value: Any) -> Any:
    """Snapshot-friendly copy: by reference for immutables, shallow or deep for containers."""
    if value is None or type(value) in _IMMUTABLE_TYPES or isinstance(value, _IMMUTABLE_BASES):
        return value
    if isinstance(value, File):
        return value.name
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, dict):
        for v in value.values():
            if v is not None and type(v) not in _IMMUTABLE_TYPES and not isinstance(v, _IMMUTABLE_BASES):
                return deepcopy(value)
        return value.copy()
    if isinstance(value, (list, tuple)):
        for v in value:
            if v is not None and type(v) not in _IMMUTABLE_TYPES and not isinstance(v, _IMMUTABLE_BASES):
                return deepcopy(value)
        return list(value) if isinstance(value, list) else value
    return deepcopy(value)


@cython.cclass
class DiffDescriptor:
    """Tracks field changes via ``__set__``. Compiled as a Cython extension type."""

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
        if type(val1) is type(val2):
            return val1 == val2
        # Different types: try field.to_python() to coerce, fall back to raw ==
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
            # Django's DeferredAttribute fetches AND populates __dict__ — re-read
            # so TRACK_MUTATIONS below also sees deferred values.
            value = self._deferred_attr.__get__(instance, cls)

        # setdefault avoids the get-then-set race under free-threading.
        if self._track_mutations and type(value) in _MUTABLE_TYPES:
            snap = d.setdefault("_state_mut_snapshot", {})
            if self._field_name not in snap:
                snap[self._field_name] = deepcopy(value)
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        if instance is None:
            return

        d = instance.__dict__
        attname = self._attname

        # ORM expressions resolve at save time; not user-visible value changes.
        if isinstance(value, (BaseExpression, Combinable)):
            d[attname] = value
            return

        try:
            state = instance._state
            if state.adding or attname not in d:
                d[attname] = value
                return
        except AttributeError:
            d[attname] = value
            return

        # Mutual exclusion between FIELDS_TO_CHECK and _EXCLUDE is enforced at
        # class def time, so at most one is set here.
        field_name = self._field_name
        cache = d.get("_fields_check_cache")
        if cache is None:
            cache = (
                getattr(instance, "FIELDS_TO_CHECK", None),
                getattr(instance, "FIELDS_TO_CHECK_EXCLUDE", None),
            )
            d["_fields_check_cache"] = cache

        fields_to_check, fields_to_exclude = cache

        if fields_to_check is not None and field_name not in fields_to_check and attname not in fields_to_check:
            d[attname] = value
            return

        if fields_to_exclude is not None and (field_name in fields_to_exclude or attname in fields_to_exclude):
            d[attname] = value
            return

        # Equality before the dict write so a raise in _values_equal leaves
        # __dict__ consistent with _state_diff.
        old = d[attname]
        equal = self._values_equal(value, old)
        d[attname] = value
        if equal:
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
