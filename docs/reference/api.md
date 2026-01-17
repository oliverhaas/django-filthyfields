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

Optional list of field names to track. If not set, all fields are tracked.

```python
class MyModel(DirtyFieldsMixin, models.Model):
    FIELDS_TO_CHECK = ['name', 'status']

    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    description = models.TextField()  # Not tracked
```

**Type:** `list[str] | None`

**Default:** `None` (track all fields)

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

#### `is_dirty(check_relationship=False, check_m2m=None)`

Check if the model instance has any unsaved changes.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields in the check |
| `check_m2m` | `dict[str, set] \| None` | `None` | Dict of M2M field names to expected PK sets (requires `ENABLE_M2M_CHECK=True`) |

**Returns:** `bool` - `True` if any tracked fields have changed

**Raises:** `ValueError` if `check_m2m` is provided but `ENABLE_M2M_CHECK` is `False`

**Example:**

```python
>>> obj = MyModel.objects.get(pk=1)
>>> obj.is_dirty()
False
>>> obj.name = "changed"
>>> obj.is_dirty()
True

# M2M check (requires ENABLE_M2M_CHECK = True)
>>> obj.tags.add(new_tag)
>>> obj.is_dirty(check_m2m={'tags': {1, 2}})  # Expected PKs
True
```

---

#### `get_dirty_fields(check_relationship=False, check_m2m=None, verbose=False)`

Get a dictionary of fields that have been modified.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |
| `check_m2m` | `dict[str, set] \| None` | `None` | Dict of M2M field names to expected PK sets (requires `ENABLE_M2M_CHECK=True`) |
| `verbose` | `bool` | `False` | Return both old and new values |

**Returns:** `dict` - Dictionary mapping field names to original values (or to `{'saved': old, 'current': new}` if verbose)

**Raises:** `ValueError` if `check_m2m` is provided but `ENABLE_M2M_CHECK` is `False`

**Example:**

```python
>>> obj.name = "new"
>>> obj.get_dirty_fields()
{'name': 'old'}

>>> obj.get_dirty_fields(verbose=True)
{'name': {'saved': 'old', 'current': 'new'}}

# M2M check (requires ENABLE_M2M_CHECK = True)
>>> obj.tags.add(new_tag)
>>> obj.get_dirty_fields(check_m2m={'tags': {1, 2}})
{'tags': {1, 2, 3}}  # Returns current DB state if different from expected
```

---

#### `was_dirty(check_relationship=False)`

Check if instance was dirty before the last save.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |

**Returns:** `bool` - `True` if any tracked fields were dirty before the last save

**Example:**

```python
>>> obj.name = "new"
>>> obj.save()
>>> obj.was_dirty()
True
```

---

#### `get_was_dirty_fields(check_relationship=False)`

Get fields that were dirty before the last save.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |

**Returns:** `dict` - Dictionary mapping field names to original values from before the last save

**Example:**

```python
>>> obj.name = "new"
>>> obj.save()
>>> obj.get_was_dirty_fields()
{'name': 'old'}
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

## Module Info

### `__version__`

The package version string.

```python
>>> from dirtyfields import __version__
>>> __version__
'1.9.8b2'
```
