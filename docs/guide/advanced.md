# Advanced Features

## Limiting Tracked Fields

### Including Specific Fields (Whitelist)

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

### Excluding Specific Fields (Blacklist)

Use `FIELDS_TO_CHECK_EXCLUDE` to track all fields except the specified ones:

```python
class MyModel(DirtyFieldsMixin, models.Model):
    FIELDS_TO_CHECK_EXCLUDE = ['updated_at', 'last_login']

    name = models.CharField(max_length=100)
    email = models.EmailField()
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True)

>>> obj.name = "changed"
>>> obj.is_dirty()
True  # 'name' is tracked

>>> obj2 = MyModel.objects.get(pk=2)
>>> obj2.updated_at = timezone.now()
>>> obj2.is_dirty()
False  # 'updated_at' is excluded!
```

This is more convenient than `FIELDS_TO_CHECK` when you want to track most fields but exclude a few (e.g., auto-updated timestamps).

!!! warning "Cannot Use Both"
    You cannot use both `FIELDS_TO_CHECK` and `FIELDS_TO_CHECK_EXCLUDE` on the same model. Attempting to do so will raise a `ValueError`.

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

### Bulk Operations

Django's `bulk_update()` and `bulk_create()` bypass the model's `save()` method, so dirty tracking doesn't happen automatically. Use the helper functions to manually manage dirty state:

```python
from filthyfields import capture_dirty_state, reset_dirty_state

# Modify multiple instances
instances = list(MyModel.objects.filter(status='pending'))
for obj in instances:
    obj.status = 'processed'

# Capture dirty state before bulk operation
capture_dirty_state(instances)

# Perform bulk update (bypasses save())
MyModel.objects.bulk_update(instances, ['status'])

# Reset dirty state after bulk operation
reset_dirty_state(instances)

# Now instances are clean, but was_dirty() still works
for obj in instances:
    print(f"{obj.pk} was dirty: {obj.was_dirty()}")
```

You can also reset only specific fields:

```python
# Only reset the 'status' field, keep other fields dirty
reset_dirty_state(instances, fields=['status'])
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

## Many-to-Many Field Tracking

M2M fields are not tracked by default because checking them requires additional database queries. To enable M2M tracking, set `ENABLE_M2M_CHECK = True`:

```python
class Article(DirtyFieldsMixin, models.Model):
    ENABLE_M2M_CHECK = True

    title = models.CharField(max_length=100)
    tags = models.ManyToManyField(Tag)
```

Then use `check_m2m=True` to include M2M fields in dirty checks:

```python
>>> article = Article.objects.get(pk=1)
>>> article.tags.all()
<QuerySet [<Tag: python>, <Tag: django>]>

# First check captures the original state
>>> article.is_dirty(check_m2m=True)
False

# Add a new tag
>>> article.tags.add(Tag.objects.get(pk=3))
>>> article.is_dirty(check_m2m=True)
True

>>> article.get_dirty_fields(check_m2m=True)
{'tags': {1, 2}}  # Original state before changes

# After save, state is re-captured
>>> article.save()
>>> article.is_dirty(check_m2m=True)
False

# was_dirty works for M2M too
>>> article.was_dirty(check_m2m=True)
True
>>> article.get_was_dirty_fields(check_m2m=True)
{'tags': {1, 2}}  # What it was before save
```

!!! warning "Performance Impact"
    M2M checking generates extra queries each time you check. The original M2M state is captured on the first `check_m2m=True` call and re-captured after each save. Only enable it when you specifically need to track M2M changes.

## Custom Comparison Functions

The default comparison uses simple equality (`==`). For special cases like timezone-aware datetime comparisons, you can provide a custom comparison function:

```python
from filthyfields import DirtyFieldsMixin, timezone_support_compare

class MyModel(DirtyFieldsMixin, models.Model):
    compare_function = (timezone_support_compare, {})

    updated_at = models.DateTimeField()
```

The `compare_function` is a tuple of `(function, kwargs)`. The function receives `(new_value, old_value, **kwargs)` and returns `True` if values are equal.

You can also write your own:

```python
def case_insensitive_compare(new_value, old_value):
    if isinstance(new_value, str) and isinstance(old_value, str):
        return new_value.lower() == old_value.lower()
    return new_value == old_value

class MyModel(DirtyFieldsMixin, models.Model):
    compare_function = (case_insensitive_compare, {})
```

## Custom Normalisation Functions

To transform values before they're returned by `get_dirty_fields()`, use a normalisation function:

```python
from datetime import datetime

def normalise_for_json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value

class MyModel(DirtyFieldsMixin, models.Model):
    normalise_function = (normalise_for_json, {})
```

This is useful when you need to serialize dirty field values, for example when logging changes to JSON.
