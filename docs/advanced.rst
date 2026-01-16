Advanced Usage
==============


Verbose mode
------------
By default, when you use ``get_dirty_fields()`` function, if there are dirty fields, only the saved value is returned.
You can use the ``verbose`` option to return the saved and current in-memory value:

.. code-block:: pycon

    >>> model = ExampleModel.objects.create(characters="first value")
    >>> model.characters = "second value"
    >>> model.get_dirty_fields()
    {'characters': 'first_value'}
    >>> model.get_dirty_fields(verbose=True)
    {'characters': {'saved': 'first value', 'current': 'second value'}}


Checking foreign key fields.
----------------------------
By default, dirty functions are not checking foreign keys. If you want to also take these relationships into account,
use ``check_relationship`` parameter:

.. code-block:: python

    class ForeignKeyModel(DirtyFieldsMixin, models.Model):
        fkey = models.ForeignKey(AnotherModel, on_delete=models.CASCADE)

.. code-block:: pycon

    >>> model = ForeignKeyModel.objects.create(fkey=obj1)
    >>> model.is_dirty()
    False
    >>> model.fkey = obj2
    >>> model.is_dirty()
    False
    >>> model.is_dirty(check_relationship=True)
    True
    >>> model.get_dirty_fields()
    {}
    >>> model.get_dirty_fields(check_relationship=True)
    {'fkey': 1}


Saving dirty fields.
--------------------
If you want to only save dirty fields from an instance in the database (only these fields will be involved in SQL query),
you can use ``save_dirty_fields()`` method. If the model instance has not been persisted yet, it will be saved in full.

Warning: This calls the ``save()`` method internally so will trigger the same signals as normally calling the ``save()`` method.

.. code-block:: pycon

    >>> model.is_dirty()
    True
    >>> model.save_dirty_fields()
    >>> model.is_dirty()
    False


Checking what was dirty before save
-----------------------------------
After saving a model, you can check what fields were dirty before the save using ``was_dirty()`` and
``get_was_dirty_fields()``:

.. code-block:: pycon

    >>> model = ExampleModel.objects.create(characters="first value")
    >>> model.characters = "second value"
    >>> model.save()
    >>> model.is_dirty()
    False
    >>> model.was_dirty()
    True
    >>> model.get_was_dirty_fields()
    {'characters': 'first value'}


Performance
-----------

``django-filthyfields`` uses a descriptor-based approach that only tracks fields when they are actually
modified. This is significantly faster than the original ``django-dirtyfields`` signal-based approach,
which captured full model state on every load.

The performance impact is minimal because:

- No ``post_init`` signal handler runs on every model load
- Only fields that are actually changed are tracked
- Original values are stored lazily on first modification

Using a Proxy Model
^^^^^^^^^^^^^^^^^^^

If you only need dirty field tracking in some places, you can use a `Proxy Model`_ to avoid
any overhead in code paths that don't need tracking:

.. _Proxy Model: https://docs.djangoproject.com/en/dev/topics/db/models/#proxy-models

.. code-block:: python

    # Base model without tracking
    class FooModel(models.Model):
        ...

    # Proxy model with tracking
    class FooModelWithDirtyFields(DirtyFieldsMixin, FooModel):
        class Meta:
            proxy = True


Database Transactions Limitations
---------------------------------
There is a limitation when using filthyfields with database transactions.
If your code saves Model instances inside a ``transaction.atomic()`` block, and the transaction is rolled back,
then the Model instance's ``is_dirty()`` method will return ``False`` when it should return ``True``.

This is because after the ``save()`` method is called, the instance's dirty state is reset because it thinks it has
successfully saved to the database. When the transaction rolls back, the database is reset but the model doesn't know.

.. code-block:: python

    model = ExampleModel.objects.create(characters="first")
    model.characters = "second"
    assert model.is_dirty()

    try:
        with transaction.atomic():
            model.save()
            assert not model.is_dirty()  # dirty state was reset
            raise DatabaseError("pretend something went wrong")
    except DatabaseError:
        pass

    # Problem: value in DB is still "first" but model thinks it's clean
    assert model.characters == "second"
    assert not model.is_dirty()  # This is wrong!

The workaround is to call ``model.refresh_from_db()`` if the transaction is rolled back.
