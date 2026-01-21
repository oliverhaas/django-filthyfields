# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml)

**Tracking dirty fields on a Django model instance.**

Dirty means that field in-memory and database values are different.

!!! info "Fork of django-dirtyfields"
    This is a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a
    rewritten "lazy" descriptor-based internal implementation and some additional small features. The goal is to eventually merge
    these improvements upstream if and once the implementation matures.

## Why This Fork?

The original django-dirtyfields captures model state by making a full snapshot of the model at the start.
This means **every field value is copied on every model load**, regardless of whether you'll modify the instance.

This fork uses **lazy descriptor-based tracking**, which for typical use-cases where one reads/writes fields at most once each has less overhead.

### Benchmark Results

Performance comparison on Python 3.14 (10,000 instances, 20 fields each):

| Scenario                              | Plain   | filthyfields | dirtyfields |
|---------------------------------------|---------|--------------|-------------|
| `.only(1 field)` + read 1 field       | 35 ms   | 41 ms (+6)   | 151 ms (+116) |
| Load 20 fields + read 20 fields       | 58 ms   | 110 ms (+52) | 244 ms (+186) |
| `.only(1 field)` + write 1 field      | 35 ms   | 47 ms (+12)  | 153 ms (+118) |
| Load 20 fields + write 20 fields      | 55 ms   | 202 ms (+147)| 244 ms (+189) |
| `.only(1 field)` + read+write 1 field | 35 ms   | 47 ms (+12)  | 152 ms (+117) |
| Load 20 fields + read+write 20 fields | 60 ms   | 223 ms (+163)| 243 ms (+183) |

Run the benchmark yourself: `uv run python tests/benchmark.py --compare`

## Versioning

This package follows the same version numbering as upstream django-dirtyfields to indicate API compatibility. For example, version 1.9.8 of django-filthyfields is API-compatible with django-dirtyfields 1.9.8. 

Note that compatibility is one-way: code using django-dirtyfields can switch to django-filthyfields, but not vice versa, since filthyfields has additional features (e.g., `was_dirty()`). 

Pre-release suffixes (e.g., `b1`) are used during development, post-release suffixes (e.g. `post1`) for fork-only bugfixes.

## Compatibility

| Django | Python                |
|--------|-----------------------|
| 4.2    | 3.11, 3.12            |
| 5.2    | 3.11, 3.12, 3.13, 3.14, 3.14t |
| 6.0    | 3.12, 3.13, 3.14, 3.14t |

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
