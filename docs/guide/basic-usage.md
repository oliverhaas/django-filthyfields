# Basic Usage

## Core Methods

### `is_dirty(check_relationship=False, check_m2m=False)`

Returns `True` if any tracked fields have been modified since the model was loaded or last saved.

```python
>>> obj = MyModel.objects.get(pk=1)
>>> obj.is_dirty()
False
>>> obj.name = "new name"
>>> obj.is_dirty()
True
```

**Parameters:**

- `check_relationship` (bool): If `True`, also checks foreign key relationships. Default: `False`.
- `check_m2m` (bool): If `True`, also checks M2M relationships. Requires `ENABLE_M2M_CHECK=True`. Default: `False`.

### `get_dirty_fields(check_relationship=False, check_m2m=False, verbose=False)`

Returns a dictionary of dirty fields with their original values.

```python
>>> obj.name = "new name"
>>> obj.get_dirty_fields()
{'name': 'old name'}
```

**Parameters:**

- `check_relationship` (bool): If `True`, includes foreign key changes. Default: `False`.
- `check_m2m` (bool): If `True`, includes M2M changes. Requires `ENABLE_M2M_CHECK=True`. Default: `False`.
- `verbose` (bool): If `True`, returns both old and new values. Default: `False`.

### `save_dirty_fields()`

Saves only the fields that have been modified, rather than all fields.

```python
>>> obj.name = "new name"
>>> obj.save_dirty_fields()  # Only updates 'name' field
```

This can be more efficient than `save()` when you've only modified a few fields on a model with many fields.

### `was_dirty(check_relationship=False)`

Check if the instance was dirty before the last save. Useful in `post_save` signals or after saving to know what changed.

```python
>>> obj.name = "new name"
>>> obj.save()
>>> obj.is_dirty()
False
>>> obj.was_dirty()
True
```

### `get_was_dirty_fields(check_relationship=False)`

Get the fields that were dirty before the last save.

```python
>>> obj.name = "new name"
>>> obj.save()
>>> obj.get_was_dirty_fields()
{'name': 'old name'}
```

This is particularly useful in signal handlers:

```python
from django.db.models.signals import post_save

def my_handler(sender, instance, **kwargs):
    if instance.was_dirty():
        changed = instance.get_was_dirty_fields()
        if 'status' in changed:
            # Status changed from changed['status'] to instance.status
            notify_status_change(instance)

post_save.connect(my_handler, sender=MyModel)
```

## Async Support

`asave()` and `arefresh_from_db()` are supported and behave the same way as their sync counterparts:

```python
await obj.asave()              # captures was_dirty, saves, then resets dirty state
await obj.arefresh_from_db()   # reloads from DB and resets dirty state
```

All check methods (`is_dirty()`, `get_dirty_fields()`, `was_dirty()`, `get_was_dirty_fields()`) are plain synchronous calls on the in-memory instance and are safe to call from async code.

## Verbose Mode

When `verbose=True`, `get_dirty_fields()` returns both old and new values:

```python
>>> obj.name = "new name"
>>> obj.get_dirty_fields(verbose=True)
{'name': {'saved': 'old name', 'current': 'new name'}}
```

## Tracking Foreign Keys

By default, foreign key changes are not tracked. Use `check_relationship=True` to include them:

```python
class Article(DirtyFieldsMixin, models.Model):
    title = models.CharField(max_length=100)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

>>> article.author = new_author
>>> article.is_dirty()  # False - FK not tracked by default
>>> article.is_dirty(check_relationship=True)  # True
>>> article.get_dirty_fields(check_relationship=True)
{'author': <Author: old_author>}
```

## File Fields

File fields (including `ImageField`) are fully supported, including tracking changes via `.save()` and `.delete()`:

```python
class Document(DirtyFieldsMixin, models.Model):
    file = models.FileField(upload_to='docs/')

>>> doc = Document.objects.get(pk=1)
>>> doc.file.save('new.txt', content)  # Tracked!
>>> doc.is_dirty()
True

>>> doc.file.delete()  # Also tracked!
>>> doc.is_dirty()
True
```

## F() Expressions

Fields assigned with `F()` expressions are properly tracked:

```python
from django.db.models import F

>>> obj.count = F('count') + 1
>>> obj.is_dirty()
True
>>> obj.get_dirty_fields()
{'count': 5}  # Original value before F() expression
```

## New (Unsaved) Models

New model instances that haven't been saved are always considered dirty:

```python
>>> obj = MyModel(name="test")
>>> obj.is_dirty()
True
>>> obj.save()
>>> obj.is_dirty()
False
```
