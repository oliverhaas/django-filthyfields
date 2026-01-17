"""Comparison utilities for dirty field tracking.

Provides functions for comparing field values, with special handling for
timezone-aware datetime fields.
"""

from __future__ import annotations

import warnings
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from django.utils import timezone as django_timezone

if TYPE_CHECKING:
    from datetime import tzinfo


def raw_compare(new_value: Any, old_value: Any) -> bool:
    """Default comparison: simple equality check."""
    return new_value == old_value


def normalise_value(value: Any) -> Any:
    """Default normalisation: returns value unchanged.

    Custom implementations can transform values for storage/display.
    For example, converting datetime objects to ISO strings for JSON.
    """
    return value


def timezone_support_compare(
    new_value: Any,
    old_value: Any,
    timezone_to_set: tzinfo = UTC,
) -> bool:
    """Compare values with timezone awareness handling for datetimes.

    When comparing datetime values, handles the case where one value is
    timezone-aware and the other is naive, converting as needed.

    Args:
        new_value: The new (current) value
        old_value: The old (saved) value
        timezone_to_set: Timezone to use when converting naive datetimes

    Returns:
        True if values are equal, False otherwise
    """
    if not (isinstance(new_value, datetime) and isinstance(old_value, datetime)):
        return raw_compare(new_value, old_value)

    db_value_is_aware = django_timezone.is_aware(old_value)
    in_memory_value_is_aware = django_timezone.is_aware(new_value)

    if db_value_is_aware == in_memory_value_is_aware:
        return raw_compare(new_value, old_value)

    if db_value_is_aware:
        # If db value is aware, it means that settings.USE_TZ=True, so we need to convert in-memory one
        warnings.warn(
            f"DateTimeField received a naive datetime ({new_value}) while time zone support is active.",
            RuntimeWarning,
            stacklevel=4,
        )
        new_value = django_timezone.make_aware(new_value, timezone_to_set).astimezone(UTC)
    else:
        # The db is not timezone aware, but the value we are passing for comparison is aware.
        warnings.warn(
            f"Time zone support is not active (settings.USE_TZ=False), "
            f"and you pass a time zone aware value ({new_value}) "
            "Converting database value before comparison.",
            RuntimeWarning,
            stacklevel=4,
        )
        old_value = django_timezone.make_aware(old_value, UTC).astimezone(timezone_to_set)

    return raw_compare(new_value, old_value)
