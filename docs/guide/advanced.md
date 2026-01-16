# Advanced Features

## Limiting Tracked Fields

Use `FIELDS_TO_CHECK` to only track specific fields:

```python
class MyModel(DirtyFieldsMixin, models.Model):
    FIELDS_TO_CHECK = ['important_field']

    important_field = models.CharField(max_length=100)
    unimportant_field = models.CharField(max_length=100)

>>> obj.important_field = "changed"
>>> obj.is_dirty()
True

>>> obj2 = MyModel.objects.get(pk=2)
>>> obj2.unimportant_field = "changed"
>>> obj2.is_dirty()
False  # Not tracked!
```

This is useful when you only care about changes to specific fields, or want to improve performance by not tracking large fields.

## Model Inheritance

### Abstract Base Classes

Dirty field tracking works with abstract base classes:

```python
class BaseModel(DirtyFieldsMixin, models.Model):
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

class Article(BaseModel):
    title = models.CharField(max_length=100)

>>> article.title = "new title"
>>> article.is_dirty()
True
```

### Proxy Models

Proxy models inherit dirty field tracking from their parent:

```python
class Article(DirtyFieldsMixin, models.Model):
    title = models.CharField(max_length=100)
    is_published = models.BooleanField(default=False)

class PublishedArticle(Article):
    class Meta:
        proxy = True

>>> published = PublishedArticle.objects.get(pk=1)
>>> published.title = "changed"
>>> published.is_dirty()
True
```

## Performance Considerations

### Descriptor-Based Tracking

Unlike the original django-dirtyfields which uses signals to capture model state on every load,
this implementation uses descriptors that only store values when fields are modified.

This means:

- **Loading models is faster**: No state copying on `post_init`
- **Memory usage is lower**: Only changed fields are stored
- **Saving models is simpler**: No `post_save` signal handler

### When to Use `save_dirty_fields()`

Use `save_dirty_fields()` instead of `save()` when:

- You've only modified a few fields on a model with many fields
- You want to minimize database write load
- You're in a tight loop updating many objects

```python
# Instead of this:
obj.status = 'completed'
obj.save()  # Updates all fields

# Do this:
obj.status = 'completed'
obj.save_dirty_fields()  # Only updates 'status'
```

## Transaction Limitations

!!! warning "Rollback Behavior"
    If a transaction is rolled back, the in-memory model state will not be automatically
    restored. The model will appear "clean" even though the database still has the old values.

```python
from django.db import transaction

obj = MyModel.objects.get(pk=1)
obj.name = "new name"

try:
    with transaction.atomic():
        obj.save()
        raise Exception("Rollback!")
except:
    pass

# obj.is_dirty() is now False, but the database has the old value!
obj.refresh_from_db()  # Use this to sync state
```

## Refreshing from Database

Use `refresh_from_db()` to reset the dirty state and reload values from the database:

```python
>>> obj.name = "new name"
>>> obj.is_dirty()
True
>>> obj.refresh_from_db()
>>> obj.is_dirty()
False
>>> obj.name
'old name'  # Restored from database
```

## Deferred Fields

When using `.only()` or `.defer()`, only the loaded fields are tracked:

```python
>>> obj = MyModel.objects.only('name').get(pk=1)
>>> obj.name = "changed"
>>> obj.is_dirty()
True
>>> obj.get_dirty_fields()
{'name': 'old name'}

# Accessing a deferred field loads it from the database
>>> obj.other_field  # Loads from DB
>>> obj.other_field = "changed"
>>> obj.get_dirty_fields()
{'name': 'old name', 'other_field': 'original value'}
```
