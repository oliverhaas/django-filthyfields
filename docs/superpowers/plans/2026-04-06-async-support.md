# Async Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit `asave()` and `arefresh_from_db()` overrides to `DirtyFieldsMixin` so dirty tracking works correctly in async Django contexts.

**Architecture:** Mirror the sync `save()` / `refresh_from_db()` methods with async counterparts that call the same pure-Python dirty-tracking hooks (`_dirty_capture_was_dirty`, `_dirty_reset_state`) around `await super().asave()` / `await super().arefresh_from_db()`. Add `pytest-asyncio` test dependency and a new `tests/test_async.py`.

**Tech Stack:** Django >=4.2, pytest-asyncio

---

### Task 1: Add pytest-asyncio dependency

**Files:**
- Modify: `pyproject.toml:43-53` (dev dependency group)

- [ ] **Step 1: Add pytest-asyncio to dev dependencies**

In `pyproject.toml`, add `"pytest-asyncio"` to the `[dependency-groups] dev` list. Place it after `pytest-django`:

```toml
dev = [
  "django-stubs==5.2.8",
  "mypy==1.16.1",
  "pre-commit==4.5.1",
  "pytest==9.0.2",
  "pytest-asyncio",
  "pytest-cov==7.0.0",
  "pytest-django==4.11.1",
  "pytest-xdist==3.8.0",
  "ruff==0.14.13",
  "ty==0.0.12",
]
```

- [ ] **Step 2: Install the new dependency**

Run: `uv sync`

Expected: Clean install with pytest-asyncio added.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add pytest-asyncio for async test support"
```

---

### Task 2: Add `asave()` override to `DirtyFieldsMixin`

**Files:**
- Modify: `src/dirtyfields/dirtyfields.py:363-366` (after `save()`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_async.py`:

```python
import pytest

from tests.models import ModelTest

pytestmark = [pytest.mark.django_db(transaction=True)]


@pytest.mark.asyncio
async def test_asave_resets_dirty_state():
    tm = await ModelTest.objects.acreate()
    assert not tm.is_dirty()

    tm.boolean = False
    assert tm.is_dirty()
    assert tm.get_dirty_fields() == {"boolean": True}

    await tm.asave()
    assert not tm.is_dirty()
    assert tm.get_dirty_fields() == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_async.py::test_asave_resets_dirty_state -v`

Expected: PASS (Django's default `asave()` bridges to our `save()` override, so the test may already pass). This confirms the bridge works, but we still add the explicit override for forward-compatibility.

- [ ] **Step 3: Add `asave()` method**

In `src/dirtyfields/dirtyfields.py`, after the `save()` method (line 366), add:

```python
    async def asave(self, *args: Any, **kwargs: Any) -> None:
        self._dirty_capture_was_dirty()
        await super().asave(*args, **kwargs)
        self._dirty_reset_state()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_async.py::test_asave_resets_dirty_state -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dirtyfields/dirtyfields.py tests/test_async.py
git commit -m "feat: add asave() override for async dirty tracking"
```

---

### Task 3: Add `asave()` was_dirty test

**Files:**
- Modify: `tests/test_async.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_async.py`:

```python
@pytest.mark.asyncio
async def test_asave_captures_was_dirty():
    tm = await ModelTest.objects.acreate(boolean=True, characters="original")

    tm.characters = "modified"
    assert tm.is_dirty()

    await tm.asave()

    assert tm.was_dirty()
    assert tm.get_was_dirty_fields() == {"characters": "original"}
    assert not tm.is_dirty()

    # Save again with no changes
    await tm.asave()
    assert not tm.was_dirty()
    assert tm.get_was_dirty_fields() == {}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_async.py::test_asave_captures_was_dirty -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_async.py
git commit -m "test: verify asave() captures was_dirty state"
```

---

### Task 4: Add `asave()` with `update_fields` test

**Files:**
- Modify: `tests/test_async.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_async.py`:

```python
@pytest.mark.asyncio
async def test_asave_with_update_fields():
    tm = await ModelTest.objects.acreate(boolean=True, characters="original")

    tm.boolean = False
    tm.characters = "modified"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "original"}

    await tm.asave(update_fields=["boolean"])

    # After partial save, only the saved field should be clean
    # Note: Django's save(update_fields=) only writes specified fields to DB
    # but dirty tracking resets ALL fields after save
    assert not tm.is_dirty()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_async.py::test_asave_with_update_fields -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_async.py
git commit -m "test: verify asave() works with update_fields"
```

---

### Task 5: Add `arefresh_from_db()` override

**Files:**
- Modify: `src/dirtyfields/dirtyfields.py:368-375` (after `refresh_from_db()`)
- Modify: `tests/test_async.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_async.py`:

```python
@pytest.mark.asyncio
async def test_arefresh_from_db_resets_dirty_state():
    tm = await ModelTest.objects.acreate(boolean=True, characters="original")
    alias = await ModelTest.objects.aget(pk=tm.pk)
    alias.boolean = False
    await alias.asave()

    # tm still has stale local state
    assert tm.boolean is True

    await tm.arefresh_from_db()
    assert tm.boolean is False
    assert tm.get_dirty_fields() == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_async.py::test_arefresh_from_db_resets_dirty_state -v`

Expected: PASS (Django's default `arefresh_from_db()` bridges to sync `refresh_from_db()`). We still add the explicit override for forward-compatibility.

- [ ] **Step 3: Add `arefresh_from_db()` method**

In `src/dirtyfields/dirtyfields.py`, after the `refresh_from_db()` method (line 375), add:

```python
    async def arefresh_from_db(  # ty: ignore[invalid-method-override]
        self,
        using: str | None = None,
        fields: Iterable[str] | None = None,
        from_queryset: models.QuerySet[Self] | None = None,
    ) -> None:
        await super().arefresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        self._dirty_reset_state(fields=fields)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_async.py::test_arefresh_from_db_resets_dirty_state -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dirtyfields/dirtyfields.py tests/test_async.py
git commit -m "feat: add arefresh_from_db() override for async dirty tracking"
```

---

### Task 6: Add `arefresh_from_db()` partial field reset test

**Files:**
- Modify: `tests/test_async.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_async.py`:

```python
@pytest.mark.asyncio
async def test_arefresh_from_db_partial_fields():
    tm = await ModelTest.objects.acreate(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    await tm.arefresh_from_db(fields=["characters"])
    assert tm.boolean is False
    assert tm.characters == "old value"
    assert tm.get_dirty_fields() == {"boolean": True}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_async.py::test_arefresh_from_db_partial_fields -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_async.py
git commit -m "test: verify arefresh_from_db() partial field reset"
```

---

### Task 7: Add `aget()` clean state test

**Files:**
- Modify: `tests/test_async.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_async.py`:

```python
@pytest.mark.asyncio
async def test_aget_produces_clean_state():
    created = await ModelTest.objects.acreate(boolean=True, characters="hello")
    tm = await ModelTest.objects.aget(pk=created.pk)

    assert not tm.is_dirty()
    assert tm.get_dirty_fields() == {}
    assert "_state_diff" not in tm.__dict__
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_async.py::test_aget_produces_clean_state -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_async.py
git commit -m "test: verify aget() produces clean dirty state"
```

---

### Task 8: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `pytest -v`

Expected: All tests pass, including new async tests and all existing tests.

- [ ] **Step 2: Run ruff and type checking**

Run: `ruff check src/ tests/ && ruff format --check src/ tests/`

Expected: No issues.
