"""Diff-based dirty field tracking for Django models — only changed fields are stored."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import FieldDoesNotExist
from django.core.files import File
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.expressions import BaseExpression, Combinable
from django.db.models.fields.files import FieldFile, FileDescriptor
from django.db.models.fields.related_descriptors import ForeignKeyDeferredAttribute
from django.db.models.query_utils import DeferredAttribute

from filthyfields._descriptor import DiffDescriptor, _normalize_value

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Self

    CompareFunction = tuple[Callable[..., bool], dict[str, Any]]
    NormaliseFunction = tuple[Callable[..., Any], dict[str, Any]]


def _should_track_field(instance: models.Model, field_name: str, field_attname: str | None = None) -> bool:
    """Apply FIELDS_TO_CHECK / FIELDS_TO_CHECK_EXCLUDE. Accepts both name and attname (e.g. 'fkey'/'fkey_id')."""
    fields_to_check = getattr(instance, "FIELDS_TO_CHECK", None)
    if fields_to_check is not None:
        return field_name in fields_to_check or (field_attname is not None and field_attname in fields_to_check)

    fields_to_exclude = getattr(instance, "FIELDS_TO_CHECK_EXCLUDE", None)
    if fields_to_exclude is not None:
        return field_name not in fields_to_exclude and (field_attname is None or field_attname not in fields_to_exclude)

    return True


def _track_file_change(instance: models.Model, field_name: str, old_name: str, new_name: str) -> None:
    if old_name == new_name:
        return
    if not _should_track_field(instance, field_name):
        return

    d = instance.__dict__
    diff = d.setdefault("_state_diff", {})
    if field_name not in diff:
        diff[field_name] = old_name
    elif new_name == diff[field_name]:
        del diff[field_name]


class _TrackingFieldFileMixin:
    """``FieldFile`` mixin that records ``save()`` / ``delete()`` into the instance's diff."""

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

    Layering preserves base-specific behaviour like ``ImageFieldFile``'s
    dimension handling.
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
    """Tracks file-field assignments. Reads use Django's ``FileDescriptor.__get__``."""

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

        # Proxy models still need descriptor install when they're the first
        # DirtyFields class in the MRO (proxying a plain Django model).
        if not hasattr(cls, "_meta") or cls._meta.abstract:  # ty: ignore[unresolved-attribute]
            return cls

        if (
            getattr(cls, "FIELDS_TO_CHECK", None) is not None
            and getattr(cls, "FIELDS_TO_CHECK_EXCLUDE", None) is not None
        ):
            raise ValueError(
                f"{cls.__name__}: cannot use both FIELDS_TO_CHECK and FIELDS_TO_CHECK_EXCLUDE on the same model",
            )

        track_mutations = bool(getattr(cls, "TRACK_MUTATIONS", False))
        for field in cls._meta.concrete_fields:  # ty: ignore[unresolved-attribute]
            attr = getattr(cls, field.attname, None)
            if type(attr) in (DeferredAttribute, ForeignKeyDeferredAttribute):
                setattr(cls, field.attname, DiffDescriptor(field, attr, track_mutations))
            elif isinstance(attr, FileDescriptor):
                # field.attr_class mutation is shared with any abstract parent;
                # don't share file fields with non-DirtyFields concrete subclasses.
                field.attr_class = _wrap_attr_class(field.attr_class)
                setattr(cls, field.attname, _FileDiffDescriptor(field))

        return cls


def _get_m2m_fields(model_class: type[models.Model]) -> list[models.ManyToManyField[Any, Any]]:
    """M2M fields excluding auto-created reverse relations."""
    return cast(
        "list[models.ManyToManyField[Any, Any]]",
        [f for f in model_class._meta.get_fields() if f.many_to_many and not f.auto_created],
    )


class DirtyFieldsMixin(models.Model, metaclass=_DirtyMeta):
    """Adds dirty-field tracking. See ``is_dirty``, ``get_dirty_fields``, ``was_dirty``."""

    class Meta:
        abstract = True

    ENABLE_M2M_CHECK = False
    # Snapshot mutable values (dict/list/set/bytearray) on first __get__ so
    # in-place mutations are detectable. Costs one deepcopy per mutable field.
    TRACK_MUTATIONS = False

    compare_function: CompareFunction | None = None
    normalise_function: NormaliseFunction | None = None

    def _dirty_capture_was_dirty(self) -> None:
        self._was_dirty_fields = self.get_dirty_fields(check_relationship=False)
        self._was_dirty_fields_rel = self.get_dirty_fields(check_relationship=True)
        if self.ENABLE_M2M_CHECK:
            self._was_dirty_fields_m2m = self._get_m2m_dirty_fields()

    def _dirty_reset_state(self, fields: Iterable[str] | None = None) -> None:
        """Reset dirty state. ``fields=None`` resets everything; otherwise accepts name or attname."""
        if fields is None:
            self.__dict__.pop("_state_diff", None)
            self.__dict__.pop("_state_diff_rel", None)
            self.__dict__.pop("_state_mut_snapshot", None)
            if self.ENABLE_M2M_CHECK and self.pk:
                self._snapshot_m2m_state()
            return
        self._dirty_reset_partial(fields)

    def _dirty_reset_partial(self, fields: Iterable[str]) -> None:
        # Normalize attnames -> names so callers can pass either form.
        normalized: set[str] = set()
        for name in fields:
            try:
                normalized.add(self._meta.get_field(name).name)
            except FieldDoesNotExist:
                normalized.add(name)

        diff = self.__dict__.get("_state_diff")
        if diff:
            for name in normalized:
                diff.pop(name, None)
            rel = self.__dict__.get("_state_diff_rel")
            if rel:
                for name in normalized:
                    rel.discard(name)
        mut_snap = self.__dict__.get("_state_mut_snapshot")
        if mut_snap:
            for name in normalized:
                mut_snap.pop(name, None)
        if self.ENABLE_M2M_CHECK and self.pk and "_original_m2m_state" in self.__dict__:
            current_m2m = self._as_dict_m2m()
            for name in normalized:
                if name in current_m2m:
                    self._original_m2m_state[name] = current_m2m[name]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self._dirty_capture_was_dirty()
        super().save(*args, **kwargs)
        self._dirty_reset_state(fields=kwargs.get("update_fields"))

    async def asave(self, *args: Any, **kwargs: Any) -> None:
        self._dirty_capture_was_dirty()
        await super().asave(*args, **kwargs)
        self._dirty_reset_state(fields=kwargs.get("update_fields"))

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
        if not self.pk:
            return {}
        return {
            field.attname: {obj.pk for obj in getattr(self, field.attname).all()}
            for field in _get_m2m_fields(self.__class__)
            if _should_track_field(self, field.name, field.attname)
        }

    def _snapshot_m2m_state(self) -> None:
        if not self.ENABLE_M2M_CHECK or not self.pk:
            return
        self._original_m2m_state = self._as_dict_m2m()

    def _get_m2m_dirty_fields(self) -> dict[str, set[Any]]:
        if not self.ENABLE_M2M_CHECK or not self.pk:
            return {}

        # Lazy snapshot on first check — first call returns {}.
        if "_original_m2m_state" not in self.__dict__:
            self._snapshot_m2m_state()
            return {}

        original = getattr(self, "_original_m2m_state", {})
        current = self._as_dict_m2m()
        return {
            field_name: original_pks
            for field_name, original_pks in original.items()
            if current.get(field_name, set()) != original_pks
        }

    def _get_mutation_dirty_fields(self) -> dict[str, Any]:
        """In-place mutations detected via TRACK_MUTATIONS snapshots; skipped if already in _state_diff."""
        snap = self.__dict__.get("_state_mut_snapshot")
        if not snap:
            return {}
        diff = self.__dict__.get("_state_diff") or {}
        d = self.__dict__
        result: dict[str, Any] = {}
        for field_name, original in snap.items():
            if field_name in diff:
                continue
            if d.get(field_name) != original:
                result[field_name] = original
        return result

    def is_dirty(self, check_relationship: bool = False, check_m2m: bool = False) -> bool:
        if self._state.adding:
            return True

        # compare_function may filter dirty fields out of get_dirty_fields();
        # defer to it so the two stay consistent.
        if getattr(self, "compare_function", None) is not None:
            return bool(
                self.get_dirty_fields(check_relationship=check_relationship, check_m2m=check_m2m),
            )

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

        if self._get_mutation_dirty_fields():
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
        """Fields changed since DB load. ``verbose=True`` returns ``{"saved": old, "current": new}`` per field."""
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

        result.update(self._get_mutation_dirty_fields())

        compare_func = getattr(self, "compare_function", None)
        if compare_func is not None and result:
            func, kwargs = compare_func
            result = {k: v for k, v in result.items() if not func(self._get_field_value_for_verbose(k), v, **kwargs)}

        if check_m2m:
            result.update(self._get_m2m_dirty_fields())

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
        normalise_func = getattr(self, "normalise_function", None)
        if normalise_func is not None:
            func, kwargs = normalise_func
            return func(value, **kwargs)
        return value

    def _get_field_value_for_verbose(self, field_name: str) -> Any:
        # __dict__ first to avoid the descriptor walk; getattr only loads deferred fields.
        try:
            value = self.__dict__[field_name]
        except KeyError:
            value = getattr(self, field_name, None)
        if isinstance(value, File):
            return value.name
        return value

    def _get_current_values(
        self,
        check_relationship: bool,
        include_pk: bool,
    ) -> dict[str, Any]:
        """Current field values; used on new (adding=True) instances."""
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
        return bool(self.get_was_dirty_fields(check_relationship=check_relationship, check_m2m=check_m2m))

    def get_was_dirty_fields(self, check_relationship: bool = False, check_m2m: bool = False) -> dict[str, Any]:
        """Fields dirty before the last save (captured by save()/asave())."""
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
        """Save with ``update_fields`` set to the dirty fields. Falls back to full ``save()`` on a new instance."""
        if self._state.adding:
            self.save()
        else:
            dirty_fields = self.get_dirty_fields(check_relationship=True)
            self.save(update_fields=list(dirty_fields))


def capture_dirty_state(instances: DirtyFieldsMixin | Iterable[DirtyFieldsMixin]) -> None:
    """Snapshot dirty state — call before ``bulk_update()`` so ``was_dirty()`` works after. Accepts a single instance or an iterable."""
    if isinstance(instances, DirtyFieldsMixin):
        instances = (instances,)
    for instance in instances:
        instance._dirty_capture_was_dirty()


def reset_dirty_state(
    instances: DirtyFieldsMixin | Iterable[DirtyFieldsMixin],
    fields: Iterable[str] | None = None,
) -> None:
    """Clear dirty state — call after ``bulk_update()``. ``fields`` accepts name or attname. Accepts a single instance or an iterable."""
    if isinstance(instances, DirtyFieldsMixin):
        instances = (instances,)
    field_list = list(fields) if fields is not None else None
    for instance in instances:
        instance._dirty_reset_state(fields=field_list)
