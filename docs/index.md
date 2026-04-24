# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml)

**Tracking dirty fields on a Django model instance.**

Dirty means that field in-memory and database values are different.

!!! info "Fork of django-dirtyfields"
    This started as a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a
    rewritten "lazy" descriptor-based internal implementation, and has since diverged with its own feature set and release cadence.

## Why This Fork?

The original django-dirtyfields captures model state by making a full snapshot of the model at the start.
This means **every field value is copied on every model load**, regardless of whether you'll modify the instance.

This fork uses **lazy descriptor-based tracking**, which for typical use-cases where one reads/writes fields at most once each has less overhead.

### Benchmark Results

Python 3.14, 10,000 instances × 20 fields, 5 iterations. Numbers in parentheses are overhead vs. plain Django.

| Scenario                              | Plain   | filthyfields        | dirtyfields         |
|---------------------------------------|--------:|--------------------:|--------------------:|
| `.only(1 field)` + read 1 field       |  38 ms  |  42 ms (+4)         | 140 ms (+101)       |
| Load 20 fields + read 20 fields       | 140 ms  | 162 ms (+22)        | 516 ms (+376)       |
| `.only(1 field)` + write 1 field      |  38 ms  |  47 ms (+9)         | 141 ms (+103)       |
| Load 20 fields + write 20 fields      | 133 ms  | 244 ms (+111)       | 518 ms (+384)       |
| `.only(1 field)` + read+write 1 field |  38 ms  |  48 ms (+10)        | 141 ms (+103)       |
| Load 20 fields + read+write 20 fields | 138 ms  | 254 ms (+116)       | 527 ms (+390)       |

Across the suite, **filthyfields overhead is 3×–28× smaller than dirtyfields overhead** — biggest on read-only paths where the Cython-backed descriptor avoids the full-model snapshot that upstream does on every load.

Run the benchmark yourself: `uv run pytest tests/test_benchmark.py -m benchmark -s`

## Compatibility

| Django | Python      |
|--------|-------------|
| 6.0    | 3.14, 3.14t |

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

- [GitHub Discussions](https://github.com/oliverhaas/django-dirtyfields/discussions) - Questions and community support
