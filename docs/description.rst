
``django-filthyfields`` is a small library for tracking dirty fields on a Django model instance.
Dirty means that a field's in-memory value is different to the saved value in the database.

This is a fork of `django-dirtyfields <https://github.com/romgar/django-dirtyfields>`_ with a
descriptor-based implementation that is significantly faster than the original signal-based approach.
