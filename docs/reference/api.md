# API Reference

## DirtyFieldsMixin

The main mixin class to add dirty field tracking to Django models.

```python
from filthyfields import DirtyFieldsMixin

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

#### `TRACK_MUTATIONS`

Detect in-place mutations of mutable field values (e.g. `obj.json_field["k"] = "v"` or `obj.tags_list.append("new")`). Off by default: the descriptor-based approach only tracks assignments via `__set__`, so mutations through a live reference go unnoticed. Enabling this snapshots mutable values (`dict`, `list`, `set`, `bytearray`) via `deepcopy` on first read, so `get_dirty_fields()` can compare and detect changes.

```python
class MyModel(DirtyFieldsMixin, models.Model):
    TRACK_MUTATIONS = True

    data = models.JSONField(default=dict)
```

**Type:** `bool`

**Default:** `False`

!!! note "Cost"
    A `deepcopy` per mutable-valued field on first read. Leave off when you only reassign fields — the default is correct and free for the common case.

---

#### `compare_function`

Custom comparison function for determining if field values have changed. Useful for timezone-aware datetime comparisons.

```python
from filthyfields import DirtyFieldsMixin, timezone_support_compare

class MyModel(DirtyFieldsMixin, models.Model):
    compare_function = (timezone_support_compare, {})

    updated_at = models.DateTimeField()
```

**Type:** `tuple[Callable[..., bool], dict[str, Any]] | None`

**Default:** `None` (uses simple equality)

---

#### `normalise_function`

Custom function to transform values before returning them from `get_dirty_fields()` and `was_dirty_fields()`. Useful when the snapshot value is in a form your application code doesn't want to handle directly — e.g. converting `Decimal` to `float` for JSON serialization, or coercing custom field types into a canonical comparable form.

```python
from decimal import Decimal

def coerce_for_json(value):
    if isinstance(value, Decimal):
        return float(value)
    return value

class MyModel(DirtyFieldsMixin, models.Model):
    normalise_function = (coerce_for_json, {})

    price = models.DecimalField(max_digits=10, decimal_places=2)
```

```python
>>> obj.price = Decimal("12.50")
>>> obj.get_dirty_fields()
{'price': 9.99}  # was Decimal('9.99'), normalised to float
```

The tuple's second element is passed as keyword arguments to the callable: `your_func(value, **kwargs)`.

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

#### `is_adding` *(property)*

Whether this instance is unsaved. Mirrors `self._state.adding`.

**Returns:** `bool` — `True` for instances that haven't been INSERTed yet

**Example:**

```python
>>> obj = MyModel(name="new")
>>> obj.is_adding
True
>>> obj.save()
>>> obj.is_adding
False
```

---

#### `was_adding` *(property)*

Whether this instance was unsaved before the last `save()` / `asave()` / `capture_dirty_state()`. Useful in `post_save` handlers to distinguish "this save was an INSERT" from "this save was an UPDATE".

**Returns:** `bool` — `False` if no save or capture has happened yet

**Example:**

```python
>>> obj = MyModel(name="new")
>>> obj.was_adding
False  # Nothing captured yet
>>> obj.save()
>>> obj.was_adding
True   # The save we just did was an INSERT
>>> obj.name = "changed"
>>> obj.save()
>>> obj.was_adding
False  # The save we just did was an UPDATE
```

---

#### `save_dirty_fields()`

Save only the fields that have been modified. On a never-saved instance (`_state.adding=True`) this falls back to a normal full `save()`, since "only changed fields" doesn't make sense for an INSERT.

**Parameters:** None

**Returns:** None

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

**Example:**

```python
>>> obj.name = "changed"
>>> obj.is_dirty()
True
>>> obj.refresh_from_db()
>>> obj.is_dirty()
False
```

---

#### `arefresh_from_db(using=None, fields=None, from_queryset=None)` *(async)*

Async equivalent of `refresh_from_db()`.

**Example:**

```python
obj.name = "changed"
await obj.arefresh_from_db()
obj.is_dirty()  # False
```

---

## Utility Functions

### `raw_compare(new_value, old_value)`

Default comparison function using simple equality.

```python
>>> from filthyfields import raw_compare
>>> raw_compare("a", "a")
True
>>> raw_compare("a", "b")
False
```

---

### `normalise_value(value)`

Default normalisation function that returns the value unchanged.

```python
>>> from filthyfields import normalise_value
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
from filthyfields import DirtyFieldsMixin, timezone_support_compare

class MyModel(DirtyFieldsMixin, models.Model):
    compare_function = (timezone_support_compare, {})
    updated_at = models.DateTimeField()
```

---

## Bulk Operation Helpers

These functions help track dirty state when using bulk operations like `bulk_update()`, which bypass the model's `save()` method.

### `capture_dirty_state(instances)`

Capture current dirty state before a bulk operation.

Call this before `bulk_update()` to preserve the dirty state for later inspection via `was_dirty()` / `get_was_dirty_fields()`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `instances` | `DirtyFieldsMixin \| Iterable[DirtyFieldsMixin]` | A single instance or an iterable of instances |

**Returns:** `None`

---

### `reset_dirty_state(instances, fields=None)`

Reset dirty tracking state after a bulk operation.

Call this after `bulk_update()` to clear the dirty state, indicating that changes have been persisted.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instances` | `DirtyFieldsMixin \| Iterable[DirtyFieldsMixin]` | - | A single instance or an iterable of instances |
| `fields` | `Iterable[str] \| None` | `None` | If provided, only reset these specific fields. Otherwise reset all. |

**Returns:** `None`

**Example:**

```python
from filthyfields import capture_dirty_state, reset_dirty_state

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
>>> from filthyfields import __version__
>>> __version__  # e.g. '1.9.8b6'
```
