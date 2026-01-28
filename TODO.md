# Django Filthyfields - TODO

Roadmap and improvement tracker for the django-filthyfields package.

## Upstream Sync

- [x] **Synced with upstream v1.9.9** (2026-01-28):
  - Added Django 6.0 F() expression tests (auto-refresh behavior)
  - Fixed flaky timezone tests (use deterministic timedelta instead of now())
  - JSONField cleanup was already done in our fork
  - Last synced: v1.9.9 (2026-01-22)

---

## Features

### High Priority

- [ ] **FIELDS_TO_CHECK_EXCLUDE**: Add alternative to `FIELDS_TO_CHECK` that excludes specified fields instead of including. More convenient when you want to track most fields except a few.
  ```python
  class MyModel(DirtyFieldsMixin, models.Model):
      FIELDS_TO_CHECK_EXCLUDE = ['updated_at', 'last_login']  # Track everything except these
  ```

### Medium Priority

- [ ] **Public API for clearing dirty state**: Expose `clear_dirty_fields(fields=None)` method to allow users to selectively reset dirty state without saving.

- [ ] **get_dirty_fields_diff()**: Convenience method returning `{field: (old_value, new_value)}` dict for easier change inspection.

### Low Priority

- [ ] **Batch dirty checking**: Add `is_any_dirty(fields)` to check if any field in a list is dirty.

- [ ] **Callback hooks**: Consider adding `on_field_dirty` / `on_field_clean` hooks for auditing/logging use cases (signals may suffice).

---

## Documentation

### High Priority

- [ ] **Fix API parameter types**: In `docs/guide/basic-usage.md`, `check_m2m` parameter shows as `None` but should be `bool`.

- [ ] **Thread-safety documentation**: Document behavior with Python 3.14t (free-threaded) and async contexts.

### Medium Priority

- [ ] **Django Admin integration guide**: How dirty tracking works with admin's queryset operations and `list_editable`.

- [ ] **Django REST Framework guide**: Integration patterns with DRF serializers and `update()` methods.

- [ ] **Migration guide from django-dirtyfields**: Document differences and how to switch from upstream.

- [ ] **Common patterns guide**:
  - Audit logging with `was_dirty()`
  - Track only critical fields for performance
  - Conditional validation based on dirty state
  - Sync to external systems on specific field changes

### Low Priority

- [ ] **Troubleshooting FAQ**: Common questions like "Why isn't my field showing as dirty?"

- [ ] **Performance tuning guide**: When to use `FIELDS_TO_CHECK`, trade-offs of tracking all fields.

- [ ] **FIELDS_TO_CHECK with M2M**: Document interaction between `FIELDS_TO_CHECK` and M2M tracking.

---

## Testing

### High Priority

- [ ] **Bulk operations**: Add tests for `bulk_create()`, `bulk_update()`, `QuerySet.update()`.

- [ ] **Custom storage backends**: Test file field tracking with custom storage classes (S3, etc).

- [ ] **Thread safety**: Add concurrency tests, especially for Python 3.14t.

### Medium Priority

- [ ] **Custom field types**: Test with third-party fields (django-phonenumber-field, django-money, etc).

- [ ] **Edge cases**:
  - Empty collections (`[]`, `{}`, `set()`)
  - Large nested JSONField structures
  - Deferred + only() combinations
  - GenericForeignKey/GenericRelation

- [ ] **Transaction rollback**: Test dirty state after transaction rollback.

- [ ] **Multi-database**: Test with `using` parameter for multi-database setups.

### Low Priority

- [ ] **Pickle support**: Test model serialization/deserialization.

- [ ] **Performance regression tests**: Automated benchmarks in CI.

---

## Code Quality

### Medium Priority

- [ ] **Refactor file field tracking**: Current monkey-patching of `FieldFile.save()` and `.delete()` is fragile. Consider:
  - Subclass FieldFile instead of monkey-patching
  - Signal-based approach for file operations
  - Add `hasattr()` guards for custom storage classes

- [ ] **Centralize state management**: Replace scattered `__dict__` entries (`_state_diff`, `_state_diff_rel`, `_original_m2m_state`, `_fields_to_check_cache`) with a dedicated `_DirtyState` class.

### Low Priority

- [ ] **Split dirtyfields.py**: Consider splitting 546-line file into:
  - `_descriptors.py` (descriptor classes)
  - `_normalization.py` (value normalization)
  - `_mixin.py` (DirtyFieldsMixin)
  - `_metaclass.py` (_DirtyMeta)

- [ ] **Type hints refinement**: Make `CompareFunction` and `NormaliseFunction` type aliases more specific.

---

## Package Naming

### Decision Needed

- [ ] **Clarify package vs import name**: Package is `django-filthyfields` on PyPI but imports are from `dirtyfields`. Options:
  1. Keep as-is (documented, maintains upstream compatibility)
  2. Create `filthyfields` alias that re-exports from `dirtyfields`
  3. Rename import path to `filthyfields` (breaking change)

  **Current decision**: Keep as-is for upstream API compatibility.

---

## Performance

### Investigated (No Action Needed)

- [x] ~~Deep copy optimization~~ - Already optimized with shallow copy for simple dicts/lists (commit a92c13d)
- [x] ~~_values_equal() optimization~~ - Already has fast-path for same-type comparison (commit ee3f98f)
- [x] ~~__set__ optimization~~ - Already has early returns and cached FIELDS_TO_CHECK (commit e190b0c)

### Low Priority

- [ ] **Descriptor instance caching**: Could cache descriptor instances in metaclass instead of creating new ones per field.

---

## CI/CD

### Completed

- [x] mypy strict mode
- [x] dependabot auto-merge
- [x] py.typed marker
- [x] Benchmarks in dedicated directory

### Low Priority

- [ ] **Add benchmark to CI**: Run performance benchmarks and fail if regression detected.

---

## Notes

### Design Decisions

1. **Descriptor-based vs Signal-based**: This fork uses descriptors instead of `post_init`/`post_save` signals. This is faster for model loading but has overhead on field access. This trade-off is intentional and documented.

2. **Lazy tracking**: Original values are only stored when a field actually changes, not on model load. This reduces memory usage but means we can't detect "unchanged" writes (setting a field to its current value).

3. **M2M tracking is explicit**: Requires `ENABLE_M2M_CHECK = True` and `check_m2m=True` on each call. This is intentional to avoid hidden database queries.

### Known Limitations

1. **Transaction rollback**: Dirty state is not automatically reset on transaction rollback (documented).

2. **QuerySet.update()**: Direct queryset updates bypass dirty tracking entirely.

3. **File field monkey-patching**: Works but relies on FieldFile having `.save()` and `.delete()` methods.
