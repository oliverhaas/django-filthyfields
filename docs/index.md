# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml)

**Tracking dirty fields on a Django model instance.**

Dirty means that field in-memory and database values are different.

!!! info "Fork of django-dirtyfields"
    This is a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a
    rewritten "lazy" descriptor-based internal implementation. The goal is to eventually merge
    these improvements upstream if and once the implementation matures.

## Why This Fork?

The original django-dirtyfields captures model state by making a full snapshot of the model at the start.
This means **every field value is copied on every model load**, regardless of whether you'll modify the instance.

This fork uses **lazy descriptor-based tracking**, which for typical use-cases where one reads/writes fields at most once each has less overhead.

### Benchmark Results

Overhead vs plain Django models (10,000 instances, 20 fields each):

| Scenario                           | filthyfields | dirtyfields |
|------------------------------------|--------------|-------------|
| `.only(1 field)` + read 1 field    | +7 ms        | +128 ms     |
| Fetch 20 fields + read 20 fields   | +53 ms       | +225 ms     |
| `.only(1 field)` + write 1 field   | +10 ms       | +126 ms     |
| Fetch 20 fields + write 20 fields  | +121 ms      | +227 ms     |

## Versioning

This package follows the same version numbering as upstream django-dirtyfields to indicate API compatibility. For example, version 1.9.8 of django-filthyfields is API-compatible with django-dirtyfields 1.9.8. Pre-release suffixes (e.g., `b1`) are used during development, post-release suffixes (e.g. `post1`) for bug fork-only bugfixes.

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
