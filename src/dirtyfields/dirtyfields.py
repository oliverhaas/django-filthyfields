"""Diff-based dirty field tracking for Django models.

Only stores original values of fields that actually change, rather than
capturing full model state upfront. Significantly faster than the signal-based approach.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.core.files import File
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.expressions import BaseExpression, Combinable
from django.db.models.fields.files import FieldFile, FileDescriptor
from django.db.models.fields.related_descriptors import ForeignKeyDeferredAttribute
from django.db.models.query_utils import DeferredAttribute

from dirtyfields._descriptor import DiffDescriptor, _normalize_value

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Self

    CompareFunction = tuple[Callable[..., bool], dict[str, Any]]
    NormaliseFunction = tuple[Callable[..., Any], dict[str, Any]]


def _should_track_field(instance: models.Model, field_name: str, field_attname: str | None = None) -> bool:
    """Check if a field should be tracked based on FIELDS_TO_CHECK or FIELDS_TO_CHECK_EXCLUDE.

    Accepts both field.name (e.g., 'fkey') and field.attname (e.g., 'fkey_id').

    FIELDS_TO_CHECK: Only track fields in this list (whitelist)
    FIELDS_TO_CHECK_EXCLUDE: Track all fields EXCEPT those in this list (blacklist)

    Mutual-exclusion validation lives on the assignment path (_DiffDescriptor.__set__);
    this helper does not raise.
    """
    fields_to_check = getattr(instance, "FIELDS_TO_CHECK", None)
    if fields_to_check is not None:
        return field_name in fields_to_check or (field_attname is not None and field_attname in fields_to_check)

    fields_to_exclude = getattr(instance, "FIELDS_TO_CHECK_EXCLUDE", None)
    if fields_to_exclude is not None:
        return field_name not in fields_to_exclude and (field_attname is None or field_attname not in fields_to_exclude)

    return True


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


class _TrackingFieldFileMixin:
    """Mixin for ``FieldFile`` subclasses that records ``save()`` / ``delete()``
    into the instance's dirty-diff.

    Installed per-field by replacing ``field.attr_class`` with a subclass
    ``(self, base_attr_class)`` at metaclass time. No monkey-patching.
    """

    def save(self, name: str, content: File[Any], save: bool = True) -> None:
        old_name = self.name or ""  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        super().save(name, content, save=save)  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
        new_name = self.name or ""  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        instance = self.instance  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        if not instance._state.adding:
            _track_file_change(instance, self.field.name, old_name, new_name)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]

    def delete(self, save: bool = True) -> None:
        old_name = self.name or ""  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        super().delete(save=save)  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
        instance = self.instance  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        if not instance._state.adding:
            _track_file_change(instance, self.field.name, old_name, "")  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]


_TRACKING_ATTR_CLASS_CACHE: dict[type[FieldFile], type[FieldFile]] = {}


def _wrap_attr_class(base: type[FieldFile]) -> type[FieldFile]:
    """Return a ``(_TrackingFieldFileMixin, base)`` subclass, cached per base.

    ``base`` is whatever ``attr_class`` the field has — typically ``FieldFile``
    for ``FileField`` or ``ImageFieldFile`` for ``ImageField``; layering via a
    synthesized subclass preserves any base-specific behaviour (e.g. image
    dimension handling).
    """
    if issubclass(base, _TrackingFieldFileMixin):
        return base
    cached = _TRACKING_ATTR_CLASS_CACHE.get(base)
    if cached is not None:
        return cached
    wrapped = cast(
        "type[FieldFile]",
        type(f"Tracking{base.__name__}", (_TrackingFieldFileMixin, base), {}),
    )
    _TRACKING_ATTR_CLASS_CACHE[base] = wrapped
    return wrapped


class _FileDiffDescriptor(FileDescriptor):
    """Tracks file-field attribute assignments. Reads go through Django's own
    ``FileDescriptor.__get__`` which produces the tracking ``FieldFile``
    subclass we install via ``field.attr_class``."""

    def __set__(self, instance: models.Model | None, value: Any) -> None:
        if instance is None:
            return

        d = instance.__dict__
        attname = self.field.attname
        field_name = self.field.name

        state = getattr(instance, "_state", None)
        should_track = (
            state is not None
            and not state.adding
            and attname in d
            and _should_track_field(instance, field_name, attname)
        )

        if should_track:
            old = d[attname]
            old_normalized = (old.name or "") if isinstance(old, File) else (old or "")
            new_normalized = (value.name or "") if isinstance(value, File) else (value or "")

            _track_file_change(instance, field_name, str(old_normalized), str(new_normalized))

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

        if hasattr(cls, "_meta") and not cls._meta.abstract:  # ty: ignore[unresolved-attribute]
            for field in cls._meta.concrete_fields:  # ty: ignore[unresolved-attribute]
                attr = getattr(cls, field.attname, None)
                if type(attr) in (DeferredAttribute, ForeignKeyDeferredAttribute):
                    setattr(cls, field.attname, DiffDescriptor(field, attr))
                elif isinstance(attr, FileDescriptor):
                    field.attr_class = _wrap_attr_class(field.attr_class)
                    setattr(cls, field.attname, _FileDiffDescriptor(field))

        return cls


def _get_m2m_fields(model_class: type[models.Model]) -> list[models.ManyToManyField[Any, Any]]:
    """Get M2M fields for a model class (excluding auto-created reverse relations)."""
    return cast(
        "list[models.ManyToManyField[Any, Any]]",
        [f for f in model_class._meta.get_fields() if f.many_to_many and not f.auto_created],
    )


class DirtyFieldsMixin(models.Model, metaclass=_DirtyMeta):
    """Mixin for Django models with dirty field tracking via descriptors.

    Key methods: is_dirty(), get_dirty_fields(), was_dirty(), get_was_dirty_fields().
    """

    class Meta:
        abstract = True

    # Set to True to enable M2M field tracking
    ENABLE_M2M_CHECK = False

    # Custom compare function: (callable, kwargs_dict) or None for default equality
    compare_function: CompareFunction | None = None

    # Custom normalise function: (callable, kwargs_dict) or None for no normalization
    # Used to transform values before returning them in get_dirty_fields()
    normalise_function: NormaliseFunction | None = None

    def _dirty_capture_was_dirty(self) -> None:
        """Capture current dirty state into _was_dirty_fields for post-save inspection."""
        self._was_dirty_fields = self.get_dirty_fields(check_relationship=False)
        self._was_dirty_fields_rel = self.get_dirty_fields(check_relationship=True)
        if self.ENABLE_M2M_CHECK:
            self._was_dirty_fields_m2m = self._get_m2m_dirty_fields()

    def _dirty_reset_state(self, fields: Iterable[str] | None = None) -> None:
        """Reset dirty tracking state.

        Args:
            fields: If provided, only reset these fields. Otherwise reset all.
        """
        if fields is None:
            self.__dict__.pop("_state_diff", None)
            self.__dict__.pop("_state_diff_rel", None)
            # Reset M2M state by re-snapshotting current state
            if self.ENABLE_M2M_CHECK and self.pk:
                self._snapshot_m2m_state()
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

    async def asave(self, *args: Any, **kwargs: Any) -> None:
        self._dirty_capture_was_dirty()
        await super().asave(*args, **kwargs)
        self._dirty_reset_state()

    def refresh_from_db(  # ty: ignore[invalid-method-override]
        self,
        using: str | None = None,
        fields: Iterable[str] | None = None,
        from_queryset: models.QuerySet[Self] | None = None,
    ) -> None:
        super().refresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        self._dirty_reset_state(fields=fields)

    async def arefresh_from_db(  # ty: ignore[invalid-method-override]
        self,
        using: str | None = None,
        fields: Iterable[str] | None = None,
        from_queryset: models.QuerySet[Self] | None = None,
    ) -> None:
        await super().arefresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        self._dirty_reset_state(fields=fields)

    def _as_dict_m2m(self) -> dict[str, set[Any]]:
        """Get current M2M field values as a dict of sets of PKs."""
        if not self.pk:
            return {}

        return {
            field.attname: {obj.pk for obj in getattr(self, field.attname).all()}
            for field in _get_m2m_fields(self.__class__)
            if _should_track_field(self, field.name, field.attname)
        }

    def _snapshot_m2m_state(self) -> None:
        """Capture current M2M state as the original state for dirty tracking."""
        if not self.ENABLE_M2M_CHECK or not self.pk:
            return
        self._original_m2m_state = self._as_dict_m2m()

    def _get_m2m_dirty_fields(self) -> dict[str, set[Any]]:
        """Get M2M fields that have changed since the original snapshot."""
        if not self.ENABLE_M2M_CHECK or not self.pk:
            return {}

        # Capture original state on first check (lazy initialization)
        if not hasattr(self, "_original_m2m_state"):
            self._snapshot_m2m_state()
            return {}  # First check - nothing dirty yet

        original = getattr(self, "_original_m2m_state", {})
        current = self._as_dict_m2m()
        result = {}

        for field_name, original_pks in original.items():
            current_pks = current.get(field_name, set())
            if current_pks != original_pks:
                result[field_name] = original_pks

        return result

    def is_dirty(self, check_relationship: bool = False, check_m2m: bool = False) -> bool:
        """Check if instance has unsaved changes."""
        if self._state.adding:
            return True
        diff = self.__dict__.get("_state_diff")
        if not diff:
            has_field_changes = False
        elif check_relationship:
            has_field_changes = True
        else:
            rel = self.__dict__.get("_state_diff_rel") or set()
            has_field_changes = any(k not in rel for k in diff)

        if has_field_changes:
            return True

        if check_m2m:
            if not self.ENABLE_M2M_CHECK:
                raise ValueError("You can't check m2m fields if ENABLE_M2M_CHECK is set to False")
            return bool(self._get_m2m_dirty_fields())

        return False

    def get_dirty_fields(
        self,
        check_relationship: bool = False,
        check_m2m: bool = False,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Get fields that have changed since load from DB.

        Args:
            check_relationship: Include FK field changes
            check_m2m: Include M2M field changes (requires ENABLE_M2M_CHECK=True)
            verbose: Return {"saved": old, "current": new} instead of just old value

        Returns:
            Dict mapping field names to original values (or verbose dicts)
        """
        if check_m2m and not self.ENABLE_M2M_CHECK:
            raise ValueError("You can't check m2m fields if ENABLE_M2M_CHECK is set to False")

        if self._state.adding:
            current = self._get_current_values(check_relationship, self.pk is not None)
            if verbose:
                return {k: {"saved": None, "current": self._normalise_output_value(v)} for k, v in current.items()}
            return current

        diff = self.__dict__.get("_state_diff")
        if not diff:
            result = {}
        elif not check_relationship:
            rel = self.__dict__.get("_state_diff_rel") or set()
            result = {k: v for k, v in diff.items() if k not in rel}
        else:
            result = dict(diff)

        # Apply compare_function to filter out fields that are actually equal
        compare_func = getattr(self, "compare_function", None)
        if compare_func is not None and result:
            func, kwargs = compare_func
            result = {k: v for k, v in result.items() if not func(self._get_field_value_for_verbose(k), v, **kwargs)}

        # M2M comparison: check against original snapshot
        if check_m2m:
            m2m_dirty = self._get_m2m_dirty_fields()
            result.update(m2m_dirty)

        if verbose:
            return {
                k: {
                    "saved": self._normalise_output_value(v),
                    "current": self._normalise_output_value(self._get_field_value_for_verbose(k)),
                }
                for k, v in result.items()
            }
        return {k: self._normalise_output_value(v) for k, v in result.items()}

    def _normalise_output_value(self, value: Any) -> Any:
        """Apply normalise_function to a value if defined."""
        normalise_func = getattr(self, "normalise_function", None)
        if normalise_func is not None:
            func, kwargs = normalise_func
            return func(value, **kwargs)
        return value

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

        for field in self._meta.concrete_fields:
            if field.primary_key and not include_pk:
                continue
            if field.remote_field and not check_relationship:
                continue
            if field.attname in deferred:
                continue
            if not _should_track_field(self, field.name, field.attname):
                continue

            value = self.__dict__.get(field.attname)
            if isinstance(value, (BaseExpression, Combinable)):
                continue

            result[field.name] = _normalize_value(value)

        return result

    def was_dirty(self, check_relationship: bool = False, check_m2m: bool = False) -> bool:
        """Check if instance was dirty before the last save."""
        return bool(self.get_was_dirty_fields(check_relationship=check_relationship, check_m2m=check_m2m))

    def get_was_dirty_fields(self, check_relationship: bool = False, check_m2m: bool = False) -> dict[str, Any]:
        """Get fields that were dirty before the last save."""
        if check_m2m and not self.ENABLE_M2M_CHECK:
            raise ValueError("You can't check m2m fields if ENABLE_M2M_CHECK is set to False")

        if check_relationship:
            result = dict(getattr(self, "_was_dirty_fields_rel", {}))
        else:
            result = dict(getattr(self, "_was_dirty_fields", {}))

        if check_m2m:
            result.update(getattr(self, "_was_dirty_fields_m2m", {}))

        return result

    def save_dirty_fields(self) -> None:
        """Save only the dirty fields (optimization for partial updates)."""
        if self._state.adding:
            self.save()
        else:
            dirty_fields = self.get_dirty_fields(check_relationship=True)
            self.save(update_fields=dirty_fields.keys())


# Standalone helper functions for bulk operations


def capture_dirty_state(instances: Iterable[DirtyFieldsMixin]) -> None:
    """Capture current dirty state for multiple instances before a bulk operation.

    Call this before bulk_update() or similar operations to preserve the
    dirty state for later inspection via was_dirty() / get_was_dirty_fields().

    Args:
        instances: Iterable of model instances with DirtyFieldsMixin

    Example:
        >>> instances = list(MyModel.objects.filter(status='pending'))
        >>> for obj in instances:
        ...     obj.status = 'processed'
        >>> capture_dirty_state(instances)
        >>> MyModel.objects.bulk_update(instances, ['status'])
        >>> reset_dirty_state(instances)
        >>> instances[0].was_dirty()
        True
    """
    for instance in instances:
        instance._dirty_capture_was_dirty()


def reset_dirty_state(
    instances: Iterable[DirtyFieldsMixin],
    fields: Iterable[str] | None = None,
) -> None:
    """Reset dirty tracking state for multiple instances after a bulk operation.

    Call this after bulk_update() or similar operations to clear the dirty
    state, indicating that changes have been persisted.

    Args:
        instances: Iterable of model instances with DirtyFieldsMixin
        fields: If provided, only reset these specific fields. Otherwise reset all.

    Example:
        >>> instances = list(MyModel.objects.filter(status='pending'))
        >>> for obj in instances:
        ...     obj.status = 'processed'
        >>> capture_dirty_state(instances)
        >>> MyModel.objects.bulk_update(instances, ['status'])
        >>> reset_dirty_state(instances)
        >>> instances[0].is_dirty()
        False
    """
    field_list = list(fields) if fields is not None else None
    for instance in instances:
        instance._dirty_reset_state(fields=field_list)
