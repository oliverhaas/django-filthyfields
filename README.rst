======================
Django Filthy Fields
======================

.. image:: https://img.shields.io/pypi/v/django-filthyfields.svg
   :alt: Published PyPI version
   :target: https://pypi.org/project/django-filthyfields/
.. image:: https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml/badge.svg
   :alt: Github Actions Test status
   :target: https://github.com/oliverhaas/django-dirtyfields/actions/workflows/ci.yml

Tracking dirty fields on a Django model instance.
Dirty means that field in-memory and database values are different.

This is a fork of `django-dirtyfields <https://github.com/romgar/django-dirtyfields>`_ with a
completely rewritten "lazy" implementation. The goal is to
eventually merge these improvements upstream once the implementation matures.

**Key differences from django-dirtyfields:**

- **Descriptor-based tracking**: Only stores original values of fields that actually change,
  rather than capturing full model state on every load. Significantly faster.
- **Simpler implementation**: No signal handlers (post_init, post_save).
- **F() expression support**: Properly tracks fields assigned with F() expressions.
- **Modern Python only**: Requires Python 3.13+ and Django 5.0+.

**Removed features** (may be re-added if needed):

- M2M field tracking (``ENABLE_M2M_CHECK``)
- Custom ``compare_function``

This package is compatible with:

+------------------------+-----------------------------------+
| Django                 | Python                            |
+========================+===================================+
| 5.0, 5.1, 5.2          | 3.13, 3.14                        |
+------------------------+-----------------------------------+


Install
=======

.. code-block:: bash

    $ pip install django-filthyfields


Usage
=====

To use ``django-filthyfields``, you need to:

- Inherit from ``DirtyFieldsMixin`` in the Django model you want to track.

.. code-block:: python

    from django.db import models
    from dirtyfields import DirtyFieldsMixin

    class ExampleModel(DirtyFieldsMixin, models.Model):
        """A simple example model to test dirty fields mixin with"""
        boolean = models.BooleanField(default=True)
        characters = models.CharField(blank=True, max_length=80)

- Use one of these 2 functions on a model instance to know if this instance is dirty, and get the dirty fields:

  * ``is_dirty()``
  * ``get_dirty_fields()``


Example
-------

.. code-block:: python

    >>> model = ExampleModel.objects.create(boolean=True, characters="first value")
    >>> model.is_dirty()
    False
    >>> model.get_dirty_fields()
    {}

    >>> model.boolean = False
    >>> model.characters = "second value"

    >>> model.is_dirty()
    True
    >>> model.get_dirty_fields()
    {'boolean': True, 'characters': 'first value'}


Consult the `full documentation <docs/>`_ for more information.
