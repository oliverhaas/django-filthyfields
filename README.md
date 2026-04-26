# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-filthyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-filthyfields/actions/workflows/ci.yml)

Tracking dirty fields on a Django model instance.
Dirty means that field in-memory and database values are different.

Started as a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a rewritten lazy, descriptor-based implementation; since diverged with its own feature set and release cadence. The mixin and method names (`DirtyFieldsMixin`, `get_dirty_fields`, …) are kept from upstream — hence the play-on-words package name.

See the [documentation](https://oliverhaas.github.io/django-filthyfields/) for more information.
