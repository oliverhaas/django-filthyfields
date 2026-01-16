import pytest
from django.db.models import F

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
def test_handle_foreignkeys_id_field_in_update_fields():
    tm1 = ModelTest.objects.create(boolean=True, characters="dummy")
    tm2 = ModelTest.objects.create(boolean=True, characters="dummy")
    tmwfk = ModelWithForeignKeyTest.objects.create(fkey=tm1)

    tmwfk.fkey = tm2
    assert tmwfk.get_dirty_fields(check_relationship=True) == {"fkey": tm1.pk}

    tmwfk.save(update_fields=["fkey_id"])
    assert tmwfk.get_dirty_fields(check_relationship=True) == {}


@pytest.mark.django_db
def test_correctly_handle_foreignkeys_id_field_in_update_fields():
    tm1 = ModelTest.objects.create(boolean=True, characters="dummy")
    tm2 = ModelTest.objects.create(boolean=True, characters="dummy")
    tmwfk = ModelWithForeignKeyTest.objects.create(fkey=tm1)

    tmwfk.fkey_id = tm2.pk
    assert tmwfk.get_dirty_fields(check_relationship=True) == {"fkey": tm1.pk}

    tmwfk.save(update_fields=["fkey"])
    assert tmwfk.get_dirty_fields(check_relationship=True) == {}


@pytest.mark.django_db
def test_f_objects_tracked():
    """F objects are tracked as dirty when assigned.

    The descriptor-based approach tracks all assignments, including F expressions.
    """
    tm = ExpressionModelTest.objects.create(counter=0)
    assert tm.counter == 0
    assert tm.get_dirty_fields() == {}

    tm.counter = F("counter") + 1
    # The descriptor tracks that counter was changed (stores old value)
    assert tm.get_dirty_fields() == {"counter": 0}

    tm.save()
    tm.refresh_from_db()
    assert tm.counter == 1

    # After refresh, we can track changes
    tm.counter = 10
    assert tm.get_dirty_fields() == {"counter": 1}
