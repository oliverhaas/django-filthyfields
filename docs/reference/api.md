# API Reference

## DirtyFieldsMixin

The main mixin class to add dirty field tracking to Django models.

```python
from dirtyfields import DirtyFieldsMixin

class MyModel(DirtyFieldsMixin, models.Model):
    ...
```

### Class Attributes

#### `FIELDS_TO_CHECK`

Optional list of field names to track (whitelist). If not set, all fields are tracked.

```python
class MyModel(DirtyFieldsMixin, models.Model):
    FIELDS_TO_CHECK = ['name', 'status']

    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    description = models.TextField()  # Not tracked
```

**Type:** `list[str] | None`

**Default:** `None` (track all fields)

!!! note "Mutual Exclusion"
    Cannot be used together with `FIELDS_TO_CHECK_EXCLUDE`. Using both will raise a `ValueError`.

---

#### `FIELDS_TO_CHECK_EXCLUDE`

Optional list of field names to exclude from tracking (blacklist). All other fields are tracked.

```python
class MyModel(DirtyFieldsMixin, models.Model):
    FIELDS_TO_CHECK_EXCLUDE = ['updated_at', 'last_login']

    name = models.CharField(max_length=100)
    email = models.EmailField()
    updated_at = models.DateTimeField(auto_now=True)  # Not tracked
    last_login = models.DateTimeField(null=True)  # Not tracked
```

**Type:** `list[str] | None`

**Default:** `None` (track all fields)

!!! note "Mutual Exclusion"
    Cannot be used together with `FIELDS_TO_CHECK`. Using both will raise a `ValueError`.

---

#### `ENABLE_M2M_CHECK`

Enable Many-to-Many field tracking. When enabled, M2M fields can be checked using the `check_m2m` parameter.

```python
class MyModel(DirtyFieldsMixin, models.Model):
    ENABLE_M2M_CHECK = True

    tags = models.ManyToManyField(Tag)
```

**Type:** `bool`

**Default:** `False`

---

#### `compare_function`

Custom comparison function for determining if field values have changed. Useful for timezone-aware datetime comparisons.

```python
from dirtyfields import DirtyFieldsMixin, timezone_support_compare

class MyModel(DirtyFieldsMixin, models.Model):
    compare_function = (timezone_support_compare, {})

    updated_at = models.DateTimeField()
```

**Type:** `tuple[Callable[..., bool], dict[str, Any]] | None`

**Default:** `None` (uses simple equality)

---

#### `normalise_function`

Custom function to transform values before returning them from `get_dirty_fields()`.

```python
from dirtyfields import DirtyFieldsMixin, normalise_value

class MyModel(DirtyFieldsMixin, models.Model):
    normalise_function = (normalise_value, {})
```

**Type:** `tuple[Callable[..., Any], dict[str, Any]] | None`

**Default:** `None` (returns values unchanged)

---

### Methods

#### `is_dirty(check_relationship=False, check_m2m=False)`

Check if the model instance has any unsaved changes.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields in the check |
| `check_m2m` | `bool` | `False` | Include M2M fields in the check (requires `ENABLE_M2M_CHECK=True`) |

**Returns:** `bool` - `True` if any tracked fields have changed

**Raises:** `ValueError` if `check_m2m=True` but `ENABLE_M2M_CHECK` is `False`

**Example:**

```python
>>> obj = MyModel.objects.get(pk=1)
>>> obj.is_dirty()
False
>>> obj.name = "changed"
>>> obj.is_dirty()
True

# M2M check (requires ENABLE_M2M_CHECK = True)
>>> obj.is_dirty(check_m2m=True)  # Captures original state on first call
False
>>> obj.tags.add(new_tag)
>>> obj.is_dirty(check_m2m=True)
True
```

---

#### `get_dirty_fields(check_relationship=False, check_m2m=False, verbose=False)`

Get a dictionary of fields that have been modified.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |
| `check_m2m` | `bool` | `False` | Include M2M fields (requires `ENABLE_M2M_CHECK=True`) |
| `verbose` | `bool` | `False` | Return both old and new values |

**Returns:** `dict` - Dictionary mapping field names to original values (or to `{'saved': old, 'current': new}` if verbose)

**Raises:** `ValueError` if `check_m2m=True` but `ENABLE_M2M_CHECK` is `False`

**Example:**

```python
>>> obj.name = "new"
>>> obj.get_dirty_fields()
{'name': 'old'}

>>> obj.get_dirty_fields(verbose=True)
{'name': {'saved': 'old', 'current': 'new'}}

# M2M check (requires ENABLE_M2M_CHECK = True)
>>> obj.get_dirty_fields(check_m2m=True)  # Captures original state on first call
{}
>>> obj.tags.add(new_tag)
>>> obj.get_dirty_fields(check_m2m=True)
{'tags': {1, 2}}  # Returns original state before changes
```

---

#### `was_dirty(check_relationship=False, check_m2m=False)`

Check if instance was dirty before the last save.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |
| `check_m2m` | `bool` | `False` | Include M2M fields (requires `ENABLE_M2M_CHECK=True`) |

**Returns:** `bool` - `True` if any tracked fields were dirty before the last save

**Raises:** `ValueError` if `check_m2m=True` but `ENABLE_M2M_CHECK` is `False`

**Example:**

```python
>>> obj.name = "new"
>>> obj.save()
>>> obj.was_dirty()
True

# M2M check (requires ENABLE_M2M_CHECK = True)
>>> obj.tags.add(new_tag)
>>> obj.save()
>>> obj.was_dirty(check_m2m=True)
True
```

---

#### `get_was_dirty_fields(check_relationship=False, check_m2m=False)`

Get fields that were dirty before the last save.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |
| `check_m2m` | `bool` | `False` | Include M2M fields (requires `ENABLE_M2M_CHECK=True`) |

**Returns:** `dict` - Dictionary mapping field names to original values from before the last save

**Raises:** `ValueError` if `check_m2m=True` but `ENABLE_M2M_CHECK` is `False`

**Example:**

```python
>>> obj.name = "new"
>>> obj.save()
>>> obj.get_was_dirty_fields()
{'name': 'old'}

# M2M check (requires ENABLE_M2M_CHECK = True)
>>> obj.tags.add(new_tag)
>>> obj.save()
>>> obj.get_was_dirty_fields(check_m2m=True)
{'tags': {1, 2}}  # Original M2M state before changes
```

---

#### `save_dirty_fields()`

Save only the fields that have been modified.

**Parameters:** None

**Returns:** None

**Raises:** `ValueError` if the model has never been saved (no primary key)

**Example:**

```python
>>> obj.name = "changed"
>>> obj.save_dirty_fields()  # Only updates 'name' column
```

---

#### `asave(*args, **kwargs)` *(async)*

Async equivalent of `Model.save()` with dirty tracking. Captures dirty state into `_was_dirty_fields`, calls `super().asave()`, then resets the dirty state.

**Example:**

```python
obj.name = "changed"
await obj.asave()
obj.is_dirty()      # False
obj.was_dirty()     # True
```

---

#### `refresh_from_db(using=None, fields=None, from_queryset=None)`

Override of `Model.refresh_from_db()` that also resets the dirty state. If `fields` is provided, only those fields have their dirty state reset.

---

#### `arefresh_from_db(using=None, fields=None, from_queryset=None)` *(async)*

Async equivalent of `refresh_from_db()`.

---

## Utility Functions

### `raw_compare(new_value, old_value)`

Default comparison function using simple equality.

```python
>>> from dirtyfields import raw_compare
>>> raw_compare("a", "a")
True
>>> raw_compare("a", "b")
False
```

---

### `normalise_value(value)`

Default normalisation function that returns the value unchanged.

```python
>>> from dirtyfields import normalise_value
>>> normalise_value({"key": "value"})
{'key': 'value'}
```

---

### `timezone_support_compare(new_value, old_value, timezone_to_set=UTC)`

Comparison function with timezone awareness handling for datetime values.

When comparing datetime values where one is timezone-aware and the other is naive, this function converts as needed and emits a warning.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `new_value` | `Any` | - | The new (current) value |
| `old_value` | `Any` | - | The old (saved) value |
| `timezone_to_set` | `tzinfo` | `UTC` | Timezone to use when converting naive datetimes |

**Returns:** `bool` - `True` if values are equal

**Example:**

```python
from dirtyfields import DirtyFieldsMixin, timezone_support_compare

class MyModel(DirtyFieldsMixin, models.Model):
    compare_function = (timezone_support_compare, {})
    updated_at = models.DateTimeField()
```

---

## Bulk Operation Helpers

These functions help track dirty state when using bulk operations like `bulk_update()`, which bypass the model's `save()` method.

### `capture_dirty_state(instances)`

Capture current dirty state for multiple instances before a bulk operation.

Call this before `bulk_update()` to preserve the dirty state for later inspection via `was_dirty()` / `get_was_dirty_fields()`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `instances` | `Iterable[DirtyFieldsMixin]` | Model instances to capture state for |

**Returns:** `None`

---

### `reset_dirty_state(instances, fields=None)`

Reset dirty tracking state for multiple instances after a bulk operation.

Call this after `bulk_update()` to clear the dirty state, indicating that changes have been persisted.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instances` | `Iterable[DirtyFieldsMixin]` | - | Model instances to reset state for |
| `fields` | `Iterable[str] \| None` | `None` | If provided, only reset these specific fields. Otherwise reset all. |

**Returns:** `None`

**Example:**

```python
from dirtyfields import capture_dirty_state, reset_dirty_state

# Modify instances
instances = list(MyModel.objects.filter(status='pending'))
for obj in instances:
    obj.status = 'processed'

# Capture state before bulk update
capture_dirty_state(instances)

# Perform bulk update
MyModel.objects.bulk_update(instances, ['status'])

# Reset state after bulk update
reset_dirty_state(instances)

# Now you can check what was changed
for obj in instances:
    if obj.was_dirty():
        print(f"Object {obj.pk} had changes: {obj.get_was_dirty_fields()}")
```

---

## Module Info

### `__version__`

The package version string. Read at import time from installed package metadata via `importlib.metadata.version("django-filthyfields")`, so it always reflects the version pip/uv resolved to.

```python
>>> from dirtyfields import __version__
>>> __version__  # e.g. '1.9.8b6'
```
