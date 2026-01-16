"""Diff-based dirty field tracking for Django models.

Only stores original values of fields that actually change, rather than
capturing full model state upfront. Significantly faster than the signal-based approach.
"""

from collections.abc import Iterable
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.core.files import File
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.expressions import BaseExpression, Combinable
from django.db.models.fields.files import FileDescriptor
from django.db.models.fields.related_descriptors import ForeignKeyDeferredAttribute
from django.db.models.query_utils import DeferredAttribute

if TYPE_CHECKING:
    from typing import Self

# Types that don't need deepcopy (immutable)
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
    )
)


def _normalize_value(value: Any) -> Any:
    """Normalize a field value for storage in the diff dict."""
    if isinstance(value, File):
        return value.name
    if isinstance(value, memoryview):
        return bytes(value)
    if value is None or type(value) in _IMMUTABLE_TYPES:
        return value
    return deepcopy(value)


def _should_track_field(instance: models.Model, field_name: str) -> bool:
    """Check if a field should be tracked based on FIELDS_TO_CHECK."""
    fields_to_check = getattr(instance, "FIELDS_TO_CHECK", None)
    return fields_to_check is None or field_name in fields_to_check


def _track_file_change(instance: models.Model, field_name: str, old_name: str, new_name: str) -> None:
    """Track a file field change in the instance's diff dict."""
    if old_name == new_name:
        return

    if not _should_track_field(instance, field_name):
        return

    d = instance.__dict__
    diff = d.setdefault("_state_diff", {})

    if field_name not in diff:
        diff[field_name] = old_name
        return

    # Check if reverting to original
    if new_name == diff[field_name]:
        del diff[field_name]


class _DiffDescriptor(DeferredAttribute):
    """Descriptor that tracks field changes on __set__.

    When a field value changes, stores the original value in instance._state_diff.
    Only tracks the first change per field (original value).
    """

    __slots__ = ("_attname", "_field", "_field_name", "_is_relation")

    def __init__(self, field: models.Field[Any, Any]) -> None:
        super().__init__(field)
        self._attname = field.attname
        self._field_name = field.name
        self._is_relation = field.remote_field is not None
        self._field = field

    def __get__(self, instance: models.Model | None, cls: type | None = None) -> Any:
        if instance is None:
            return self
        val = instance.__dict__.get(self._attname)
        if val is not None:
            return val
        if self._attname in instance.__dict__:
            return None
        return super().__get__(instance, cls)

    def __set__(self, instance: models.Model | None, value: Any) -> None:
        if instance is None:
            return

        d = instance.__dict__
        attname = self._attname
        field_name = self._field_name

        state = getattr(instance, "_state", None)
        should_track = (
            state is not None and not state.adding and attname in d and _should_track_field(instance, field_name)
        )
        old = d[attname] if should_track else None

        d[attname] = value

        if not should_track or value == old:
            return

        if self._is_relation and self._field.is_cached(instance):
            self._field.delete_cached_value(instance)

        diff = d.setdefault("_state_diff", {})

        if field_name not in diff:
            diff[field_name] = _normalize_value(old)
            if self._is_relation:
                d.setdefault("_state_diff_rel", set()).add(field_name)
            return

        if _normalize_value(value) != diff[field_name]:
            return

        del diff[field_name]
        if self._is_relation and (rel := d.get("_state_diff_rel")):
            rel.discard(field_name)


class _FileDiffDescriptor(FileDescriptor):
    """Descriptor for file fields that tracks changes and returns tracking-aware FieldFile."""

    def __get__(self, instance: models.Model | None, cls: type | None = None) -> Any:
        if instance is None:
            return self

        file = super().__get__(instance, cls)

        # Wrap the FieldFile's save and delete methods to track changes
        # Note: empty FieldFile is falsy, so we check 'is not None' instead of 'if file'
        if file is not None and not getattr(file, "_dirty_wrapped", False):
            original_save = file.save
            original_delete = file.delete
            field_name = self.field.name
            inst = instance  # Capture for closure with narrowed type

            def tracked_save(name: str, content: File, save: bool = True) -> None:
                old_name = file.name or ""
                original_save(name, content, save=save)
                new_name = file.name or ""
                if not inst._state.adding:
                    _track_file_change(inst, field_name, old_name, new_name)

            def tracked_delete(save: bool = True) -> None:
                old_name = file.name or ""
                original_delete(save=save)
                if not inst._state.adding:
                    _track_file_change(inst, field_name, old_name, "")

            file.save = tracked_save
            file.delete = tracked_delete
            file._dirty_wrapped = True

        return file

    def __set__(self, instance: models.Model | None, value: Any) -> None:
        if instance is None:
            return

        d = instance.__dict__
        attname = self.field.attname
        field_name = self.field.name

        state = getattr(instance, "_state", None)
        should_track = (
            state is not None and not state.adding and attname in d and _should_track_field(instance, field_name)
        )

        if should_track:
            old = d[attname]
            old_normalized = old.name if isinstance(old, File) else (old or "")
            new_normalized = value.name if isinstance(value, File) else (value or "")

            _track_file_change(instance, field_name, old_normalized, new_normalized)

        super().__set__(instance, value)


class _DirtyMeta(ModelBase):
    """Metaclass that installs diff-tracking descriptors on model fields."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        if hasattr(cls, "_meta") and not cls._meta.abstract:
            for field in cls._meta.concrete_fields:
                attr = getattr(cls, field.attname, None)
                if type(attr) in (DeferredAttribute, ForeignKeyDeferredAttribute):
                    setattr(cls, field.attname, _DiffDescriptor(field))
                elif isinstance(attr, FileDescriptor):
                    setattr(cls, field.attname, _FileDiffDescriptor(field))

        return cls


class DirtyFieldsMixin(models.Model, metaclass=_DirtyMeta):
    """Mixin for Django models with dirty field tracking via descriptors.

    Key methods: is_dirty(), get_dirty_fields(), was_dirty(), get_was_dirty_fields().
    """

    class Meta:
        abstract = True

    _was_dirty_fields: dict[str, Any] = {}
    _was_dirty_fields_rel: dict[str, Any] = {}

    def _dirty_capture_was_dirty(self) -> None:
        """Capture current dirty state into _was_dirty_fields for post-save inspection."""
        self._was_dirty_fields = self.get_dirty_fields(check_relationship=False)
        self._was_dirty_fields_rel = self.get_dirty_fields(check_relationship=True)

    def _dirty_reset_state(self, fields: Iterable[str] | None = None) -> None:
        """Reset dirty tracking state.

        Args:
            fields: If provided, only reset these fields. Otherwise reset all.
        """
        if fields is None:
            self.__dict__.pop("_state_diff", None)
            self.__dict__.pop("_state_diff_rel", None)
        else:
            diff = self.__dict__.get("_state_diff")
            if diff:
                for name in fields:
                    diff.pop(name, None)
                rel = self.__dict__.get("_state_diff_rel")
                if rel:
                    for name in fields:
                        rel.discard(name)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self._dirty_capture_was_dirty()
        super().save(*args, **kwargs)
        self._dirty_reset_state()

    def refresh_from_db(
        self,
        using: str | None = None,
        fields: Iterable[str] | None = None,
        from_queryset: "models.QuerySet[Self, Self] | None" = None,
    ) -> None:
        super().refresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        self._dirty_reset_state(fields=fields)

    def is_dirty(self, check_relationship: bool = False) -> bool:
        """Check if instance has unsaved changes."""
        if self._state.adding:
            return True
        diff = self.__dict__.get("_state_diff")
        if not diff:
            return False
        if check_relationship:
            return True
        rel = self.__dict__.get("_state_diff_rel") or set()
        return any(k not in rel for k in diff)

    def get_dirty_fields(
        self,
        check_relationship: bool = False,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Get fields that have changed since load from DB.

        Args:
            check_relationship: Include FK field changes
            verbose: Return {"saved": old, "current": new} instead of just old value

        Returns:
            Dict mapping field names to original values (or verbose dicts)
        """
        if self._state.adding:
            current = self._get_current_values(check_relationship, self.pk is not None)
            if verbose:
                return {k: {"saved": None, "current": v} for k, v in current.items()}
            return current

        diff = self.__dict__.get("_state_diff")
        if not diff:
            return {}

        if not check_relationship:
            rel = self.__dict__.get("_state_diff_rel") or set()
            diff = {k: v for k, v in diff.items() if k not in rel}

        if verbose:
            return {k: {"saved": v, "current": self._get_field_value_for_verbose(k)} for k, v in diff.items()}
        return dict(diff)

    def _get_field_value_for_verbose(self, field_name: str) -> Any:
        """Get current field value for verbose mode, normalizing file fields."""
        value = getattr(self, field_name, None)
        if isinstance(value, File):
            return value.name
        return value

    def _get_current_values(
        self,
        check_relationship: bool,
        include_pk: bool,
    ) -> dict[str, Any]:
        """Get current field values (for new instances)."""
        result = {}
        deferred = self.get_deferred_fields()
        fields_to_check = getattr(self, "FIELDS_TO_CHECK", None)

        for field in self._meta.concrete_fields:
            if field.primary_key and not include_pk:
                continue
            if field.remote_field and not check_relationship:
                continue
            if field.attname in deferred:
                continue
            if fields_to_check is not None and field.name not in fields_to_check:
                continue

            value = self.__dict__.get(field.attname)
            if isinstance(value, (BaseExpression, Combinable)):
                continue

            result[field.name] = _normalize_value(value)

        return result

    def was_dirty(self, check_relationship: bool = False) -> bool:
        """Check if instance was dirty before the last save."""
        return bool(self.get_was_dirty_fields(check_relationship=check_relationship))

    def get_was_dirty_fields(self, check_relationship: bool = False) -> dict[str, Any]:
        """Get fields that were dirty before the last save."""
        return self._was_dirty_fields_rel if check_relationship else self._was_dirty_fields

    def save_dirty_fields(self) -> None:
        """Save only the dirty fields (optimization for partial updates)."""
        if self._state.adding:
            self.save()
        else:
            dirty_fields = self.get_dirty_fields(check_relationship=True)
            self.save(update_fields=dirty_fields.keys())
