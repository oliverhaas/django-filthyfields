# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-filthyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-filthyfields/actions/workflows/ci.yml)

**Tracking dirty fields on a Django model instance.**

Dirty means that field in-memory and database values are different.

!!! info "Originated as a fork of django-dirtyfields"
    This project started as a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a rewritten lazy, descriptor-based internal implementation. It has since diverged with its own feature set, release cadence, and import name (`filthyfields`).

## Why This Project?

The original django-dirtyfields captures model state by snapshotting every field on instance initialization — every field value is copied on every model load, regardless of whether you'll modify the instance.

This project uses lazy descriptor-based tracking instead, which for typical use cases (read or write each field at most once) has less overhead.

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

Across the suite, filthyfields overhead is 3×–28× smaller than dirtyfields overhead — biggest on read-only paths where the Cython-backed descriptor avoids the full-model snapshot that upstream does on every load.

Run the benchmark yourself: `uv run pytest tests/test_benchmark.py -m benchmark -s`

## Compatibility

| Django | Python      |
|--------|-------------|
| 6.0    | 3.14, 3.14t |

## Quick Example

```python
from django.db import models
from filthyfields import DirtyFieldsMixin

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

- [GitHub Discussions](https://github.com/oliverhaas/django-filthyfields/discussions) - Questions and community support
