"""Coverage matrix for direct-assignment dirty tracking across Django builtin
field types. This is the broad regression net: per field type, with reasonable
old/new values, verify the descriptor records the right baseline.

Path-specific behaviour (FieldFile.save, M2M add/remove, FK by id vs object,
JSON in-place mutation under TRACK_MUTATIONS) lives in test_core.py and the
respective per-feature test files — those need bespoke setup.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

import pytest

from tests.models import AllFieldTypesModel

# Field name → (initial value used for object creation, value to assign that
# differs from the initial). Each row exercises:
#   1. _normalize_value for the initial value (stored as the dirty baseline)
#   2. _values_equal between the initial and new value (must report not equal)
ORIGINAL_VALUES: dict[str, Any] = {
    "boolean": True,
    "char": "hello",
    "text": "long text here",
    "slug": "my-slug",
    "email": "a@example.com",
    "url": "https://example.com",
    "integer": 42,
    "big_integer": 10**15,
    "small_integer": 7,
    "positive_integer": 100,
    "float_value": 3.14,
    "decimal": Decimal("1.23"),
    "date": datetime.date(2024, 1, 1),
    "datetime": datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC),
    "time": datetime.time(12, 0),
    "duration": datetime.timedelta(days=1),
    "uuid": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "binary": b"abc",
    "json": {"a": 1},
    "ip": "127.0.0.1",
    "file_path": "a.txt",
}

NEW_VALUES: dict[str, Any] = {
    "boolean": False,
    "char": "world",
    "text": "different text",
    "slug": "other-slug",
    "email": "b@example.com",
    "url": "https://other.example.com",
    "integer": 99,
    "big_integer": 10**16,
    "small_integer": 8,
    "positive_integer": 200,
    "float_value": 2.71,
    "decimal": Decimal("4.56"),
    "date": datetime.date(2025, 6, 15),
    "datetime": datetime.datetime(2025, 6, 15, 9, 30, tzinfo=datetime.UTC),
    "time": datetime.time(9, 30),
    "duration": datetime.timedelta(hours=2),
    "uuid": uuid.UUID("00000000-0000-0000-0000-000000000002"),
    "binary": b"xyz",
    "json": {"a": 2, "b": [1, 2]},
    "ip": "10.0.0.1",
    "file_path": "b.txt",
}

FIELD_NAMES = list(ORIGINAL_VALUES)


@pytest.fixture
def saved_obj() -> AllFieldTypesModel:
    """Instance with every field set to its ORIGINAL_VALUES entry, then refreshed
    from DB so the in-memory state matches what the ORM rehydrates."""
    obj = AllFieldTypesModel.objects.create(**ORIGINAL_VALUES)
    obj.refresh_from_db()
    return obj


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", FIELD_NAMES)
def test_field_assign_different_value_marks_dirty(saved_obj: AllFieldTypesModel, field_name: str) -> None:
    setattr(saved_obj, field_name, NEW_VALUES[field_name])

    expected_baseline = ORIGINAL_VALUES[field_name]
    assert saved_obj.get_dirty_fields() == {field_name: expected_baseline}


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", FIELD_NAMES)
def test_field_assign_same_value_stays_clean(saved_obj: AllFieldTypesModel, field_name: str) -> None:
    setattr(saved_obj, field_name, ORIGINAL_VALUES[field_name])

    assert saved_obj.get_dirty_fields() == {}


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", FIELD_NAMES)
def test_field_assign_then_revert_clears_dirty(saved_obj: AllFieldTypesModel, field_name: str) -> None:
    """A → B → A returns to clean (the diff-deletion path in DiffDescriptor)."""
    original = ORIGINAL_VALUES[field_name]

    setattr(saved_obj, field_name, NEW_VALUES[field_name])
    assert saved_obj.get_dirty_fields() == {field_name: original}

    setattr(saved_obj, field_name, original)
    assert saved_obj.get_dirty_fields() == {}


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", FIELD_NAMES)
def test_field_assign_none_to_value_marks_dirty(field_name: str) -> None:
    obj = AllFieldTypesModel.objects.create()
    obj.refresh_from_db()
    assert getattr(obj, field_name) is None

    setattr(obj, field_name, NEW_VALUES[field_name])

    assert obj.get_dirty_fields() == {field_name: None}


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", FIELD_NAMES)
def test_field_assign_value_to_none_marks_dirty(saved_obj: AllFieldTypesModel, field_name: str) -> None:
    setattr(saved_obj, field_name, None)

    assert saved_obj.get_dirty_fields() == {field_name: ORIGINAL_VALUES[field_name]}
