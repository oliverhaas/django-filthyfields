# Async Support for django-filthyfields

**Date:** 2026-04-06
**Branch:** feat/async-support

## Problem

`DirtyFieldsMixin` hooks into `save()` and `refresh_from_db()` — both sync-only. Django 4.1+ provides `asave()` and `arefresh_from_db()`. Without explicit overrides, async callers rely on Django's `sync_to_async` bridge, which works today but is an implicit contract with Django internals.

## Approach

Mirror the sync methods with async counterparts. The dirty-tracking hooks (`_dirty_capture_was_dirty`, `_dirty_reset_state`) are pure-Python dict operations — no I/O, no async needed. They're called synchronously before/after the awaited super call.

## Mixin Changes

Two new methods on `DirtyFieldsMixin`:

### `asave()` — placed after `save()`

```python
async def asave(self, *args, **kwargs):
    self._dirty_capture_was_dirty()
    await super().asave(*args, **kwargs)
    self._dirty_reset_state()
```

### `arefresh_from_db()` — placed after `refresh_from_db()`

```python
async def arefresh_from_db(self, using=None, fields=None, from_queryset=None):
    await super().arefresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
    self._dirty_reset_state(fields=fields)
```

## Tests

New file `tests/test_async.py` using `pytest-asyncio`:

1. `asave()` resets dirty state
2. `asave()` captures was_dirty
3. `arefresh_from_db()` resets dirty state
4. `arefresh_from_db()` partial field reset
5. `aget()` produces clean state
6. `asave()` with `update_fields`

All tests use existing `ModelTest`. No new models needed.

## Dependencies

- `pytest-asyncio` added as test dependency

## Out of Scope

- `save_dirty_fields()` async variant (niche optimization)
- Async M2M tracking (`_get_m2m_dirty_fields()` does DB queries — separate concern)
- `capture_dirty_state()` / `reset_dirty_state()` — bulk helpers, already pure-Python and async-safe
