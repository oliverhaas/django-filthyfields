# Quick Start

## Add the Mixin to Your Model

To track dirty fields on a model, inherit from `DirtyFieldsMixin`:

```python
from django.db import models
from filthyfields import DirtyFieldsMixin

class ExampleModel(DirtyFieldsMixin, models.Model):
    boolean = models.BooleanField(default=True)
    characters = models.CharField(blank=True, max_length=80)
```

!!! important "Mixin Order"
    `DirtyFieldsMixin` should come **before** `models.Model` in the inheritance list.

## Check if a Model is Dirty

Use `is_dirty()` to check if any fields have been modified:

```python
>>> model = ExampleModel.objects.create(boolean=True, characters="first value")
>>> model.is_dirty()
False

>>> model.boolean = False
>>> model.is_dirty()
True
```

## Get Dirty Fields

Use `get_dirty_fields()` to get a dictionary of changed fields with their **original** values:

```python
>>> model = ExampleModel.objects.create(boolean=True, characters="first value")
>>> model.boolean = False
>>> model.characters = "second value"

>>> model.get_dirty_fields()
{'boolean': True, 'characters': 'first value'}
```

The returned dictionary maps field names to their **original** (database) values, not the new values.

## Save and Reset

After saving, the dirty state is cleared:

```python
>>> model.is_dirty()
True
>>> model.save()
>>> model.is_dirty()
False
>>> model.get_dirty_fields()
{}
```
