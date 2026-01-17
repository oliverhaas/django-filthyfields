# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml)

**Tracking dirty fields on a Django model instance.**

Dirty means that field in-memory and database values are different.

!!! info "Fork of django-dirtyfields"
    This is a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a
    completely rewritten "lazy" descriptor-based implementation. The goal is to eventually merge
    these improvements upstream if and once the implementation matures.

## Why This Fork?

The original django-dirtyfields uses Django signals (`post_init`, `post_save`) to capture model state.
This means **every field value is copied on every model load**, regardless of whether you'll modify the instance.

This fork uses **lazy descriptor-based tracking**:

- Only stores original values of fields that **actually change**
- No signal handlers means faster model instantiation
- Best for workloads where most loaded instances aren't modified

### Benchmark Results

Overhead vs plain Django models (1000 instances, 10 fields each):

| Operation        | Overhead |
|-----------------|----------|
| Load from DB    | ~50%     |
| Write 1 field   | ~70%     |
| Write 10 fields | ~150%    |
| Read 10 fields  | ~65%     |

The overhead comes from custom descriptors. However, compared to signal-based django-dirtyfields,
this approach avoids the cost of eagerly copying all field values on every model load.

Run the benchmark yourself: `uv run python tests/benchmark.py`

## Key Differences from django-dirtyfields

- **Descriptor-based tracking**: Only stores original values of fields that actually change,
  rather than capturing full model state on every load.
- **Simpler implementation**: No signal handlers (post_init, post_save).
- **F() expression support**: Properly tracks fields assigned with F() expressions.
- **Modern Python only**: Requires Python 3.13+ and Django 5.0+.

## Removed Features

The following features from django-dirtyfields are not currently supported (may be re-added if needed):

- M2M field tracking (`ENABLE_M2M_CHECK`)
- Custom `compare_function`

## Compatibility

| Django       | Python       |
|--------------|--------------|
| 5.0, 5.1, 5.2 | 3.13, 3.14   |

## Quick Example

```python
from django.db import models
from dirtyfields import DirtyFieldsMixin

class MyModel(DirtyFieldsMixin, models.Model):
    name = models.CharField(max_length=100)
    count = models.IntegerField(default=0)

# Create and save a model
obj = MyModel.objects.create(name="test", count=5)
obj.is_dirty()  # False

# Modify it
obj.name = "changed"
obj.is_dirty()  # True
obj.get_dirty_fields()  # {'name': 'test'}
```

## Getting Help

- [GitHub Issues](https://github.com/oliverhaas/django-dirtyfields/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/oliverhaas/django-dirtyfields/discussions) - Questions and community support
