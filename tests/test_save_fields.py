import django
import pytest
from django.db.models import F, Value
from django.db.models.functions import Concat

from filthyfields import DirtyStateNotCapturedError
from tests.models import (
    ExpressionModelTest,
    MixedFieldsModelTest,
    ModelTest,
    ModelWithForeignKeyTest,
)
from tests.utils import assert_number_of_queries_on_regex


@pytest.mark.django_db
def test_save_dirty_simple_field():
    tm = ModelTest.objects.create()

    tm.characters = "new_character"

    with assert_number_of_queries_on_regex(r".*characters.*", 1):
        with assert_number_of_queries_on_regex(r".*boolean.*", 1):
            tm.save()

    tm.characters = "new_character_2"

    # Naive checking on fields involved in Django query
    # boolean unchanged field is not updated on Django update query
    with assert_number_of_queries_on_regex(r".*characters.*", 1):
        with assert_number_of_queries_on_regex(r".*boolean.*", 0):
            tm.save_dirty_fields()

    assert tm.get_dirty_fields() == {}
    assert ModelTest.objects.get(pk=tm.pk).characters == "new_character_2"


@pytest.mark.django_db
def test_save_dirty_related_field():
    tm1 = ModelTest.objects.create()
    tm2 = ModelTest.objects.create()
    tmfm = MixedFieldsModelTest.objects.create(fkey=tm1)

    tmfm.fkey = tm2

    with assert_number_of_queries_on_regex(r".*fkey_id.*", 1):
        with assert_number_of_queries_on_regex(r".*characters.*", 1):
            tmfm.save()

    tmfm.fkey = tm1

    # characters unchanged field is not updated on Django update query
    with assert_number_of_queries_on_regex(r".*fkey_id.*", 1):
        with assert_number_of_queries_on_regex(r".*characters.*", 0):
            tmfm.save_dirty_fields()

    assert tmfm.get_dirty_fields() == {}
    assert MixedFieldsModelTest.objects.get(pk=tmfm.pk).fkey_id == tm1.id


@pytest.mark.django_db
def test_save_dirty_full_save_on_adding():
    tm = ModelTest()
    tm.save_dirty_fields()
    assert tm.pk
    assert tm.get_dirty_fields() == {}


@pytest.mark.django_db
def test_save_with_update_fields_only_resets_those_fields():
    """Partial save via update_fields should only reset dirty state for the saved fields.

    The unsaved fields were not persisted to the DB, so they must remain dirty
    so the user can later issue a full save() (or another partial save) to commit them.
    """
    tm = ModelTest.objects.create(boolean=True, characters="abc")
    tm.boolean = False
    tm.characters = "xyz"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "abc"}

    tm.save(update_fields=["boolean"])

    # `boolean` was persisted — clean
    # `characters` was NOT persisted — still dirty
    assert tm.get_dirty_fields() == {"characters": "abc"}

    tm.save(update_fields=["characters"])
    assert tm.get_dirty_fields() == {}


@pytest.mark.django_db
def test_fk_assigned_by_object_saved_with_id_in_update_fields():
    """Assign FK via the object descriptor, save with the `_id` form in update_fields."""
    tm1 = ModelTest.objects.create(boolean=True, characters="dummy")
    tm2 = ModelTest.objects.create(boolean=True, characters="dummy")
    tmwfk = ModelWithForeignKeyTest.objects.create(fkey=tm1)

    tmwfk.fkey = tm2
    assert tmwfk.get_dirty_fields(check_relationship=True) == {"fkey": tm1.pk}

    tmwfk.save(update_fields=["fkey_id"])
    assert tmwfk.get_dirty_fields(check_relationship=True) == {}


@pytest.mark.django_db
def test_fk_assigned_by_id_saved_with_name_in_update_fields():
    """Assign FK via `_id`, save with the field name in update_fields."""
    tm1 = ModelTest.objects.create(boolean=True, characters="dummy")
    tm2 = ModelTest.objects.create(boolean=True, characters="dummy")
    tmwfk = ModelWithForeignKeyTest.objects.create(fkey=tm1)

    tmwfk.fkey_id = tm2.pk
    assert tmwfk.get_dirty_fields(check_relationship=True) == {"fkey": tm1.pk}

    tmwfk.save(update_fields=["fkey"])
    assert tmwfk.get_dirty_fields(check_relationship=True) == {}


@pytest.mark.django_db
def test_save_dirty_reset_false_keeps_dirty_fields():
    """save(dirty_reset=False) persists the row but leaves dirty state intact for post-save inspection."""
    tm = ModelTest.objects.create(boolean=True, characters="original")
    tm.characters = "modified"
    assert tm.get_dirty_fields() == {"characters": "original"}

    tm.save(dirty_reset=False)

    # Row was persisted...
    assert ModelTest.objects.get(pk=tm.pk).characters == "modified"
    # ...but the diff is still readable.
    assert tm.get_dirty_fields() == {"characters": "original"}
    # Capture still ran by default.
    assert tm.get_was_dirty_fields() == {"characters": "original"}


@pytest.mark.django_db
def test_save_dirty_capture_false_skips_was_dirty_capture():
    """save(dirty_capture=False) skips the was_dirty snapshot but still resets by default."""
    # Build (don't create) so no capture has ever run for this instance.
    tm = ModelTest(boolean=True, characters="original")

    tm.save(dirty_capture=False)

    # Nothing was captured for this save.
    with pytest.raises(DirtyStateNotCapturedError):
        tm.was_dirty()
    # Reset still ran by default.
    assert tm.get_dirty_fields() == {}
    assert ModelTest.objects.get(pk=tm.pk).characters == "original"


@pytest.mark.django_db
def test_save_dirty_capture_false_preserves_prior_capture():
    """A skipped capture must not clobber the snapshot from an earlier save."""
    tm = ModelTest.objects.create(boolean=True, characters="original")
    tm.characters = "first"
    tm.save()
    assert tm.get_was_dirty_fields() == {"characters": "original"}

    tm.characters = "second"
    tm.save(dirty_capture=False)

    # Prior capture is untouched.
    assert tm.get_was_dirty_fields() == {"characters": "original"}


@pytest.mark.django_db
def test_save_dirty_kwargs_not_forwarded_to_django():
    """dirty_capture / dirty_reset are consumed here, not passed to Django's save()."""
    tm = ModelTest.objects.create(boolean=True, characters="original")
    tm.boolean = False
    tm.characters = "modified"

    # Combined with a real Django kwarg to prove they coexist without leaking.
    tm.save(update_fields=["boolean"], dirty_capture=False, dirty_reset=False)

    refreshed = ModelTest.objects.get(pk=tm.pk)
    assert refreshed.boolean is False
    # `characters` was excluded from update_fields, so it was not persisted.
    assert refreshed.characters == "original"
    # Reset was skipped, so the full diff is still present.
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "original"}


@pytest.mark.django_db
def test_f_objects_not_tracked():
    """F objects and other ORM expressions aren't tracked — Django evaluates them at save time."""
    tm = ExpressionModelTest.objects.create(counter=0)
    assert tm.counter == 0
    assert tm.get_dirty_fields() == {}

    tm.counter = F("counter") + 1
    assert tm.get_dirty_fields() == {}

    tm.save()
    tm.refresh_from_db()
    assert tm.counter == 1

    tm.counter = 10
    assert tm.get_dirty_fields() == {"counter": 1}


@pytest.mark.skipif(django.VERSION < (6, 0), reason="tests Django 6.0+ F() auto-refresh behavior")
@pytest.mark.django_db
def test_f_objects_auto_refresh_django6():
    """In Django 6.0+, F() assignments are auto-refreshed after save().

    https://docs.djangoproject.com/en/dev/ref/models/expressions/#f-assignments-are-refreshed-after-model-save
    """
    tm = ExpressionModelTest.objects.create(counter=0)
    assert tm.counter == 0
    assert tm.get_dirty_fields() == {}

    tm.counter = F("counter") + 1
    assert tm.get_dirty_fields() == {}

    tm.save()
    # Django 6.0 auto-refreshes F() fields after save - no manual refresh needed
    assert tm.counter == 1
    assert tm.get_dirty_fields() == {}

    # Normal tracking works
    tm.counter = 10
    assert tm.get_dirty_fields() == {"counter": 1}


@pytest.mark.skipif(django.VERSION < (6, 0), reason="tests Django 6.0+ F() auto-refresh behavior")
@pytest.mark.django_db
def test_f_objects_with_update_fields_django6():
    """F() with update_fields specified - Django 6.0+ behavior."""
    tm = ExpressionModelTest.objects.create(counter=0)
    assert tm.get_dirty_fields() == {}

    tm.counter = F("counter") + 1
    assert tm.get_dirty_fields() == {}

    tm.save(update_fields={"counter"})
    # Auto-refresh happens even with update_fields in Django 6.0+
    assert tm.counter == 1
    assert tm.get_dirty_fields() == {}

    tm.counter = 10
    assert tm.get_dirty_fields() == {"counter": 1}


@pytest.mark.skipif(django.VERSION < (6, 0), reason="tests Django 6.0+ F() behavior")
@pytest.mark.django_db
def test_concat_expression_django6():
    """Test Concat F() expression with Django 6.0+ auto-refresh."""
    tm = ModelTest.objects.create(boolean=True, characters="abc")
    assert tm.get_dirty_fields() == {}

    # Set characters to a Concat expression
    tm.characters = Concat(F("characters"), Value("def"))
    assert tm.get_dirty_fields() == {}

    # Save - Django 6.0 auto-refreshes F() fields
    tm.save()
    assert tm.characters == "abcdef"
    assert tm.get_dirty_fields() == {}

    # Normal tracking works after save
    tm.characters = "xyz"
    assert tm.get_dirty_fields() == {"characters": "abcdef"}


@pytest.mark.skipif(django.VERSION < (6, 0), reason="tests Django 6.0+ F() behavior")
@pytest.mark.django_db
def test_expression_with_update_fields_for_different_field_django6():
    """An F-bearing field isn't refreshed when save(update_fields=...) excludes it."""
    tm = ModelTest.objects.create(boolean=True, characters="abc")
    assert tm.get_dirty_fields() == {}

    tm.characters = Concat(F("characters"), Value("def"))
    assert tm.get_dirty_fields() == {}

    # Save a different field — auto-refresh skips `characters` since it's not in update_fields.
    tm.save(update_fields={"boolean"})
    assert tm.get_dirty_fields() == {}

    # Final full save resolves the expression and refreshes.
    tm.save()
    assert tm.characters == "abcdef"
    assert tm.get_dirty_fields() == {}

    tm.characters = "xyz"
    assert tm.get_dirty_fields() == {"characters": "abcdef"}
