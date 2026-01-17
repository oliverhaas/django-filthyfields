# Django Filthy Fields

[![PyPI version](https://img.shields.io/pypi/v/django-filthyfields.svg)](https://pypi.org/project/django-filthyfields/)
[![CI](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml)

Tracking dirty fields on a Django model instance.
Dirty means that field in-memory and database values are different.

This is a fork of [django-dirtyfields](https://github.com/romgar/django-dirtyfields) with a
rewritten "lazy" descriptor-based internal implementation.

See the [documentation](https://oliverhaas.github.io/django-dirtyfields/) for installation, usage, and API reference.
