# cython: language_level=3  # noqa: ERA001
"""Cython-optimized __set__ for dirty field tracking.

This module provides a faster __set__ implementation when compiled with Cython.
It works as regular Python when Cython is not available.

To compile:
    cythonize -i src/dirtyfields/_fast_set.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import cython

if TYPE_CHECKING:
    from collections.abc import Callable

if cython.compiled:
    print("dirtyfields: Using Cython-optimized __set__")  # noqa: T201


@cython.cfunc
@cython.inline
def _fast_values_equal(field: Any, val1: Any, val2: Any) -> cython.bint:
    """Compare values - fast path for same types."""
    if type(val1) is type(val2):
        return val1 == val2
    try:
        return field.to_python(val1) == field.to_python(val2)
    except Exception:  # noqa: BLE001
        return val1 == val2


def fast_set(  # noqa: PLR0913
    instance: Any,
    value: Any,
    attname: str,
    field_name: str,
    is_relation: cython.bint,
    field: Any,
    normalize_func: Callable[[Any], Any],
) -> None:
    """Fast __set__ implementation that can be compiled with Cython.

    This is the core logic extracted from _DiffDescriptor.__set__.
    """
    if instance is None:
        return

    d: dict[str, Any] = instance.__dict__

    # Fast path: check if we should track at all
    try:
        state = instance._state
        if state.adding or attname not in d:
            d[attname] = value
            return
    except AttributeError:
        d[attname] = value
        return

    # Check FIELDS_TO_CHECK (cached at instance level for speed)
    fields_to_check = d.get("_fields_to_check_cache")
    if fields_to_check is None:
        fields_to_check = getattr(instance, "FIELDS_TO_CHECK", None)
        d["_fields_to_check_cache"] = fields_to_check

    if fields_to_check is not None and field_name not in fields_to_check and attname not in fields_to_check:
        d[attname] = value
        return

    old: Any = d[attname]
    d[attname] = value

    if _fast_values_equal(field, value, old):
        return

    if is_relation and field.is_cached(instance):
        field.delete_cached_value(instance)

    diff: dict[str, Any] = d.setdefault("_state_diff", {})

    if field_name not in diff:
        diff[field_name] = normalize_func(old)
        if is_relation:
            d.setdefault("_state_diff_rel", set()).add(field_name)
        return

    # Check if reverting to original value
    if _fast_values_equal(field, value, diff[field_name]):
        del diff[field_name]
        if is_relation:
            rel = d.get("_state_diff_rel")
            if rel:
                rel.discard(field_name)
