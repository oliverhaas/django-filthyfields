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

### `is_adding` / `was_adding`

Properties for inspecting the create-vs-update state of an instance. `is_adding` mirrors `self._state.adding`; `was_adding` reports the state captured before the last save (or `capture_dirty_state()`), so a `post_save` handler can tell an INSERT from an UPDATE:

```python
>>> obj = MyModel(name="new")
>>> obj.is_adding, obj.was_adding
(True, False)
>>> obj.save()
>>> obj.is_adding, obj.was_adding
(False, True)
```

This is particularly useful in signal handlers:

```python
from django.db.models.signals import post_save

def my_handler(sender, instance, **kwargs):
    if instance.was_adding:
        notify_created(instance)
    elif instance.was_dirty():
        changed = instance.get_was_dirty_fields()
        if 'status' in changed:
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

`F()` (and other ORM expressions like `Concat`, `Func`) are not reported as dirty — they're directives the ORM resolves at save time, not values to diff against.

```python
from django.db.models import F

>>> obj.count
5
>>> obj.count = F('count') + 1
>>> obj.is_dirty()
False
```

On Django 6.0+, `save()` [auto-refreshes expression-assigned fields](https://docs.djangoproject.com/en/6.0/ref/models/expressions/#f-assignments-are-refreshed-after-model-save), so tracking resumes after the save:

```python
>>> obj.save()
>>> obj.count
6
>>> obj.count = 10
>>> obj.get_dirty_fields()
{'count': 6}
```

`save(update_fields={...})` skips the auto-refresh for fields not in `update_fields` — the unresolved expression sticks around until the next full save or `refresh_from_db()`.

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
