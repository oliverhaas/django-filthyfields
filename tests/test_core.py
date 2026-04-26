import django
import pytest
from django.db import DatabaseError, transaction

import filthyfields
from filthyfields import capture_dirty_state, reset_dirty_state
from tests.models import (
    FileFieldModel,
    JSONFieldModel,
    JSONFieldTrackMutationsModel,
    ModelTest,
    ModelWithBothFieldsConfig,
    ModelWithFieldsToCheck,
    ModelWithFieldsToCheckExclude,
    ModelWithForeignKeyTest,
    ModelWithOneToOneFieldTest,
    OrdinaryModelTest,
    OrdinaryWithDirtyFieldsProxy,
    SubclassModelTest,
)


def test_version_numbers():
    assert isinstance(filthyfields.__version__, str)
    assert filthyfields.__version__  # Not empty


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


@pytest.mark.django_db
def test_fields_to_check():
    """Test FIELDS_TO_CHECK limits which fields are tracked."""
    tm = ModelWithFieldsToCheck.objects.create()
    assert tm.get_dirty_fields() == {}

    # Change both fields
    tm.boolean1 = False
    tm.boolean2 = False

    # Only boolean1 should be tracked (it's in FIELDS_TO_CHECK)
    assert tm.get_dirty_fields() == {"boolean1": True}
    assert tm.is_dirty()


@pytest.mark.django_db
def test_fields_to_check_on_new_instance():
    """Test FIELDS_TO_CHECK with new unsaved instances."""
    tm = ModelWithFieldsToCheck()

    # Only boolean1 should be reported as dirty
    dirty = tm.get_dirty_fields()
    assert "boolean1" in dirty
    assert "boolean2" not in dirty


@pytest.mark.django_db
def test_fields_to_check_revert():
    """Test reverting a tracked field clears dirty state."""
    tm = ModelWithFieldsToCheck.objects.create()

    tm.boolean1 = False
    assert tm.get_dirty_fields() == {"boolean1": True}

    # Revert to original
    tm.boolean1 = True
    assert tm.get_dirty_fields() == {}
    assert not tm.is_dirty()


# FIELDS_TO_CHECK_EXCLUDE tests


@pytest.mark.django_db
def test_fields_to_check_exclude():
    """Test FIELDS_TO_CHECK_EXCLUDE excludes specific fields from tracking."""
    tm = ModelWithFieldsToCheckExclude.objects.create()
    assert tm.get_dirty_fields() == {}

    # Change both fields
    tm.boolean1 = False
    tm.boolean2 = False

    # Only boolean1 should be tracked (boolean2 is in FIELDS_TO_CHECK_EXCLUDE)
    assert tm.get_dirty_fields() == {"boolean1": True}
    assert tm.is_dirty()


@pytest.mark.django_db
def test_fields_to_check_exclude_on_new_instance():
    """Test FIELDS_TO_CHECK_EXCLUDE with new unsaved instances."""
    tm = ModelWithFieldsToCheckExclude()

    # Only boolean1 should be reported as dirty (boolean2 is excluded)
    dirty = tm.get_dirty_fields()
    assert "boolean1" in dirty
    assert "boolean2" not in dirty


@pytest.mark.django_db
def test_fields_to_check_exclude_revert():
    """Test reverting a tracked field clears dirty state with FIELDS_TO_CHECK_EXCLUDE."""
    tm = ModelWithFieldsToCheckExclude.objects.create()

    tm.boolean1 = False
    assert tm.get_dirty_fields() == {"boolean1": True}

    # Revert to original
    tm.boolean1 = True
    assert tm.get_dirty_fields() == {}
    assert not tm.is_dirty()


@pytest.mark.django_db
def test_fields_to_check_exclude_excluded_field_not_dirty():
    """Test that changes to excluded fields are not tracked."""
    tm = ModelWithFieldsToCheckExclude.objects.create()

    # Change only the excluded field
    tm.boolean2 = False

    # No fields should be dirty
    assert tm.get_dirty_fields() == {}
    assert not tm.is_dirty()


@pytest.mark.django_db
def test_both_fields_to_check_and_exclude_raises_error():
    """Test that using both FIELDS_TO_CHECK and FIELDS_TO_CHECK_EXCLUDE raises ValueError."""
    tm = ModelWithBothFieldsConfig.objects.create()

    # Changing a field should trigger the error on descriptor access
    with pytest.raises(ValueError, match="Cannot use both FIELDS_TO_CHECK and FIELDS_TO_CHECK_EXCLUDE"):
        tm.boolean1 = False


# Bulk operation helper tests


@pytest.mark.django_db
def test_capture_and_reset_dirty_state_with_bulk_update():
    """Test capture_dirty_state and reset_dirty_state with bulk_update."""
    # Create some instances
    instances = [ModelTest.objects.create(characters=f"obj{i}") for i in range(3)]

    # Modify them
    for i, obj in enumerate(instances):
        obj.characters = f"modified{i}"

    # Verify they're dirty
    assert all(obj.is_dirty() for obj in instances)

    # Capture dirty state before bulk update
    capture_dirty_state(instances)

    # Perform bulk update
    ModelTest.objects.bulk_update(instances, ["characters"])

    # Reset dirty state after bulk update
    reset_dirty_state(instances)

    # Verify they're no longer dirty
    assert all(not obj.is_dirty() for obj in instances)

    # Verify was_dirty works
    assert all(obj.was_dirty() for obj in instances)
    assert all(obj.get_was_dirty_fields() == {"characters": f"obj{i}"} for i, obj in enumerate(instances))


@pytest.mark.django_db
def test_reset_dirty_state_with_specific_fields():
    """Test reset_dirty_state with specific fields only."""
    tm = ModelTest.objects.create(boolean=True, characters="original")

    # Modify both fields
    tm.boolean = False
    tm.characters = "modified"

    assert tm.get_dirty_fields() == {"boolean": True, "characters": "original"}

    # Reset only the characters field
    reset_dirty_state([tm], fields=["characters"])

    # boolean should still be dirty, characters should not
    assert tm.get_dirty_fields() == {"boolean": True}


@pytest.mark.django_db
def test_capture_dirty_state_empty_list():
    """Test capture_dirty_state with empty list doesn't error."""
    capture_dirty_state([])  # Should not raise


@pytest.mark.django_db
def test_reset_dirty_state_empty_list():
    """Test reset_dirty_state with empty list doesn't error."""
    reset_dirty_state([])  # Should not raise


@pytest.mark.django_db
def test_bulk_helpers_with_generator():
    """Test that bulk helpers work with generators/iterables."""
    instances = [ModelTest.objects.create(characters=f"obj{i}") for i in range(3)]

    for obj in instances:
        obj.characters = "modified"

    # Use generator expression
    capture_dirty_state(obj for obj in instances)
    ModelTest.objects.bulk_update(instances, ["characters"])
    reset_dirty_state(obj for obj in instances)

    # Verify reset worked (note: generators are exhausted, so we check instances directly)
    assert all(not obj.is_dirty() for obj in instances)


@pytest.mark.django_db
def test_track_mutations_off_misses_in_place_mutation():
    """Without TRACK_MUTATIONS, in-place mutation of a mutable field value is not detected."""
    obj = JSONFieldModel.objects.create(json_field={"k": 1})
    obj = JSONFieldModel.objects.get(pk=obj.pk)

    obj.json_field["k"] = 2  # mutate in place, no __set__

    assert obj.is_dirty() is False
    assert obj.get_dirty_fields() == {}


@pytest.mark.django_db
def test_track_mutations_on_detects_in_place_mutation():
    """With TRACK_MUTATIONS = True, in-place mutations are detected."""
    obj = JSONFieldTrackMutationsModel.objects.create(json_field={"k": 1})
    obj = JSONFieldTrackMutationsModel.objects.get(pk=obj.pk)

    _ = obj.json_field  # first read snapshots the value
    obj.json_field["k"] = 2

    assert obj.is_dirty() is True
    assert obj.get_dirty_fields() == {"json_field": {"k": 1}}

    obj.save()
    assert obj.is_dirty() is False
    assert obj.get_dirty_fields() == {}
