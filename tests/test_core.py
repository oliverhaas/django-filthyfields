import django
import pytest
from django.db import DatabaseError, transaction

import dirtyfields
from tests.models import (
    FileFieldModel,
    ModelTest,
    ModelWithForeignKeyTest,
    ModelWithOneToOneFieldTest,
    OrdinaryModelTest,
    OrdinaryWithDirtyFieldsProxy,
    SubclassModelTest,
)


def test_version_numbers():
    assert isinstance(dirtyfields.__version__, str)
    assert isinstance(dirtyfields.VERSION, tuple)
    assert all(isinstance(number, int) for number in dirtyfields.VERSION)


@pytest.mark.django_db
def test_is_dirty_function():
    tm = ModelTest.objects.create()

    # If the object has just been saved in the db, fields are not dirty
    assert tm.get_dirty_fields() == {}
    assert not tm.is_dirty()

    # As soon as we change a field, it becomes dirty
    tm.boolean = False

    assert tm.get_dirty_fields() == {"boolean": True}
    assert tm.is_dirty()


@pytest.mark.django_db
def test_dirty_fields():
    tm = ModelTest()

    # New unsaved instances are considered dirty (all fields)
    assert tm.is_dirty()
    dirty = tm.get_dirty_fields()
    assert "boolean" in dirty
    assert "characters" in dirty

    tm.save()

    # Saving them make them not dirty anymore
    assert tm.get_dirty_fields() == {}

    # Changing values should flag them as dirty again
    tm.boolean = False
    tm.characters = "testing"

    assert tm.get_dirty_fields() == {"boolean": True, "characters": ""}

    # Resetting them to original values should unflag
    tm.boolean = True
    assert tm.get_dirty_fields() == {"characters": ""}


@pytest.mark.django_db
def test_dirty_fields_for_notsaved_pk():
    tm = ModelTest(id=1)

    # Initial state is dirty (new instance)
    assert tm.is_dirty()
    dirty = tm.get_dirty_fields()
    assert "id" in dirty
    assert "boolean" in dirty
    assert "characters" in dirty

    tm.save()

    # Saving them make them not dirty anymore
    assert tm.get_dirty_fields() == {}


@pytest.mark.django_db
def test_relationship_option_for_foreign_key():
    tm1 = ModelTest.objects.create()
    tm2 = ModelTest.objects.create()
    tm = ModelWithForeignKeyTest.objects.create(fkey=tm1)

    # Let's change the foreign key value and see what happens
    tm.fkey = tm2

    # Default dirty check is not taking foreign keys into account
    assert tm.get_dirty_fields() == {}

    # But if we use 'check_relationships' param, then foreign keys are compared
    assert tm.get_dirty_fields(check_relationship=True) == {"fkey": tm1.pk}


@pytest.mark.django_db
def test_relationship_option_for_one_to_one_field():
    tm1 = ModelTest.objects.create()
    tm2 = ModelTest.objects.create()
    tm = ModelWithOneToOneFieldTest.objects.create(o2o=tm1)

    # Let's change the one to one field and see what happens
    tm.o2o = tm2

    # Default dirty check is not taking onetoone fields into account
    assert tm.get_dirty_fields() == {}

    # But if we use 'check_relationships' param, then one to one fields are compared
    assert tm.get_dirty_fields(check_relationship=True) == {"o2o": tm1.pk}


@pytest.mark.django_db
def test_non_local_fields():
    subclass = SubclassModelTest.objects.create(characters="foo")
    subclass.characters = "spam"

    assert subclass.get_dirty_fields() == {"characters": "foo"}


@pytest.mark.django_db
def test_verbose_mode():
    tm = ModelTest.objects.create()
    tm.boolean = False

    assert tm.get_dirty_fields(verbose=True) == {"boolean": {"saved": True, "current": False}}


@pytest.mark.django_db
def test_verbose_mode_on_adding():
    tm = ModelTest()

    dirty = tm.get_dirty_fields(verbose=True)
    assert dirty["boolean"] == {"saved": None, "current": True}
    assert dirty["characters"] == {"saved": None, "current": ""}


@pytest.mark.django_db
def test_refresh_from_db():
    tm = ModelTest.objects.create()
    alias = ModelTest.objects.get(pk=tm.pk)
    alias.boolean = False
    alias.save()

    tm.refresh_from_db()
    assert tm.get_dirty_fields() == {}


@pytest.mark.django_db
def test_refresh_from_db_particular_fields():
    tm = ModelTest.objects.create(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    tm.refresh_from_db(fields={"characters"})
    assert tm.boolean is False
    assert tm.characters == "old value"
    assert tm.get_dirty_fields() == {"boolean": True}


@pytest.mark.django_db
def test_refresh_from_db_no_fields():
    tm = ModelTest.objects.create(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    tm.refresh_from_db(fields=set())
    assert tm.boolean is False
    assert tm.characters == "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}


@pytest.mark.django_db
def test_refresh_from_db_position_args():
    tm = ModelTest.objects.create(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    tm.refresh_from_db("default", {"boolean", "characters"})
    assert tm.boolean is True
    assert tm.characters == "old value"
    assert tm.get_dirty_fields() == {}


@pytest.mark.skipif(django.VERSION < (5, 1), reason="requires django 5.1 or higher")
@pytest.mark.django_db
def test_refresh_from_db_with_from_queryset():
    tm = ModelTest.objects.create(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    tm.refresh_from_db(fields={"characters"}, from_queryset=ModelTest.objects.all())
    assert tm.boolean is False
    assert tm.characters == "old value"
    assert tm.get_dirty_fields() == {"boolean": True}


@pytest.mark.skipif(django.VERSION < (5, 1), reason="requires django 5.1 or higher")
@pytest.mark.django_db
def test_refresh_from_db_position_args_with_queryset():
    tm = ModelTest.objects.create(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    tm.refresh_from_db("default", {"characters"}, ModelTest.objects.all())
    assert tm.boolean is False
    assert tm.characters == "old value"
    assert tm.get_dirty_fields() == {"boolean": True}


@pytest.mark.django_db
def test_file_fields_direct_assignment():
    """Test file field tracking via direct assignment."""
    tm = FileFieldModel()
    assert tm.is_dirty()
    tm.save()
    assert tm.get_dirty_fields() == {}

    # Direct assignment triggers the descriptor
    tm.file1 = "path/to/file.txt"
    assert tm.get_dirty_fields() == {"file1": ""}
    tm.save()
    assert tm.get_dirty_fields() == {}

    # Change file path
    tm.file1 = "path/to/other.txt"
    assert tm.get_dirty_fields() == {"file1": "path/to/file.txt"}


@pytest.mark.django_db
def test_file_fields_save_method():
    """Test file field tracking via FieldFile.save() method."""
    from django.core.files.base import ContentFile

    tm = FileFieldModel()
    tm.save()
    assert tm.get_dirty_fields() == {}

    # Use FieldFile.save() - should be tracked
    tm.file1.save("test-file-1.txt", ContentFile(b"Test content"), save=False)
    assert tm.get_dirty_fields(verbose=True) == {"file1": {"current": "file1/test-file-1.txt", "saved": ""}}
    tm.save()
    assert tm.get_dirty_fields() == {}

    # Change file via save()
    tm.file1.save("test-file-2.txt", ContentFile(b"New content"), save=False)
    assert tm.get_dirty_fields(verbose=True) == {
        "file1": {"current": "file1/test-file-2.txt", "saved": "file1/test-file-1.txt"},
    }
    tm.save()
    assert tm.get_dirty_fields() == {}


@pytest.mark.django_db
def test_transaction_behavior():
    """This test is to document the behavior in transactions"""
    tm = ModelTest.objects.create(boolean=True, characters="first")
    assert not tm.is_dirty()

    tm.characters = "second"
    assert tm.get_dirty_fields() == {"characters": "first"}

    try:
        with transaction.atomic():
            tm.save()
            assert not tm.is_dirty()
            assert tm.get_dirty_fields() == {}
            raise DatabaseError("pretend something went wrong")
    except DatabaseError:
        pass

    # Value in DB is still "first" but model does not think its dirty.
    # This is expected - after failed transaction call refresh_from_db()
    assert tm.characters == "second"
    assert not tm.is_dirty()
    assert tm.get_dirty_fields() == {}

    tm.refresh_from_db()
    assert tm.characters == "first"
    assert tm.get_dirty_fields() == {}
    tm.characters = "third"
    assert tm.is_dirty()
    assert tm.get_dirty_fields() == {"characters": "first"}


@pytest.mark.django_db
def test_proxy_model_behavior():
    tm = OrdinaryModelTest.objects.create()

    dirty_tm = OrdinaryWithDirtyFieldsProxy.objects.get(id=tm.id)
    assert not dirty_tm.is_dirty()
    assert dirty_tm.get_dirty_fields() == {}

    dirty_tm.boolean = False
    dirty_tm.characters = "hello"
    assert dirty_tm.is_dirty()
    assert dirty_tm.get_dirty_fields() == {"characters": "", "boolean": True}

    dirty_tm.save()
    assert not dirty_tm.is_dirty()
    assert dirty_tm.get_dirty_fields() == {}

    tm.refresh_from_db()
    assert tm.boolean is False
    assert tm.characters == "hello"


@pytest.mark.django_db
def test_was_dirty_after_save():
    """Test that was_dirty() returns True after save if fields were modified."""
    tm = ModelTest.objects.create(boolean=True, characters="original")

    # After create(), was_dirty reflects the pre-save state (new instance = all dirty)
    assert tm.was_dirty()

    # Make a change
    tm.characters = "modified"
    assert tm.is_dirty()

    tm.save()

    # After second save, was_dirty should reflect that we changed 'characters'
    assert tm.was_dirty()
    assert tm.get_was_dirty_fields() == {"characters": "original"}
    assert not tm.is_dirty()

    # Save again with no changes
    tm.save()
    assert not tm.was_dirty()
    assert tm.get_was_dirty_fields() == {}


@pytest.mark.django_db
def test_was_dirty_with_relationship():
    """Test was_dirty with relationship checking."""
    tm1 = ModelTest.objects.create()
    tm2 = ModelTest.objects.create()
    tm = ModelWithForeignKeyTest.objects.create(fkey=tm1)

    tm.fkey = tm2
    tm.save()

    assert tm.was_dirty(check_relationship=True)
    assert tm.get_was_dirty_fields(check_relationship=True) == {"fkey": tm1.pk}
    assert not tm.was_dirty(check_relationship=False)
