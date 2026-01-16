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

### Methods

#### `is_dirty(check_relationship=False)`

Check if the model instance has any unsaved changes.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields in the check |

**Returns:** `bool` - `True` if any tracked fields have changed

**Example:**

```python
>>> obj = MyModel.objects.get(pk=1)
>>> obj.is_dirty()
False
>>> obj.name = "changed"
>>> obj.is_dirty()
True
```

---

#### `get_dirty_fields(check_relationship=False, verbose=False)`

Get a dictionary of fields that have been modified.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_relationship` | `bool` | `False` | Include foreign key fields |
| `verbose` | `bool` | `False` | Return both old and new values |

**Returns:** `dict` - Dictionary mapping field names to original values (or to `{'saved': old, 'current': new}` if verbose)

**Example:**

```python
>>> obj.name = "new"
>>> obj.get_dirty_fields()
{'name': 'old'}

>>> obj.get_dirty_fields(verbose=True)
{'name': {'saved': 'old', 'current': 'new'}}
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

## Module Info

### `__version__`

The package version string.

```python
>>> from dirtyfields import __version__
>>> __version__
'0.1.0a2'
```

### `VERSION`

The package version as a tuple.

```python
>>> from dirtyfields import VERSION
>>> VERSION
(0, 1, 0)
```
