import pytest

from .models import (
    M2MModelWithCustomPKOnM2MTest,
    Many2ManyModelTest,
    Many2ManyWithoutMany2ManyModeEnabledModelTest,
    ModelTest,
    ModelWithCustomPKTest,
    ModelWithoutM2MCheckTest,
)


@pytest.mark.django_db
def test_dirty_fields_on_m2m():
    """Test M2M dirty field tracking with eager snapshot."""
    tm = Many2ManyModelTest.objects.create()
    tm2 = ModelTest.objects.create()
    tm3 = ModelTest.objects.create()

    # First check captures the original state (empty)
    assert tm.get_dirty_fields(check_m2m=True) == {}

    # Add an M2M relation - should now be dirty
    tm.m2m_field.add(tm2)
    assert tm.get_dirty_fields(check_m2m=True) == {"m2m_field": set()}

    # After save, M2M state is re-snapshotted
    tm.save()
    assert tm.get_dirty_fields(check_m2m=True) == {}

    # Add another relation - dirty again
    tm.m2m_field.add(tm3)
    assert tm.get_dirty_fields(check_m2m=True) == {"m2m_field": {tm2.id}}

    # Remove original - still dirty (different from saved state)
    tm.m2m_field.remove(tm2)
    assert tm.get_dirty_fields(check_m2m=True) == {"m2m_field": {tm2.id}}


@pytest.mark.django_db
def test_m2m_was_dirty_after_save():
    """Test that was_dirty works correctly for M2M fields."""
    tm = Many2ManyModelTest.objects.create()
    tm2 = ModelTest.objects.create()

    # Capture initial state
    assert tm.get_dirty_fields(check_m2m=True) == {}

    # Make changes
    tm.m2m_field.add(tm2)
    assert tm.is_dirty(check_m2m=True)
    assert tm.get_dirty_fields(check_m2m=True) == {"m2m_field": set()}

    # Save and check was_dirty
    tm.save()
    assert not tm.is_dirty(check_m2m=True)
    assert tm.was_dirty(check_m2m=True)
    assert tm.get_was_dirty_fields(check_m2m=True) == {"m2m_field": set()}


@pytest.mark.django_db
def test_dirty_fields_on_m2m_not_possible_if_not_enabled():
    tm = Many2ManyWithoutMany2ManyModeEnabledModelTest.objects.create()
    tm2 = ModelTest.objects.create()
    tm.m2m_field.add(tm2)

    with pytest.raises(ValueError, match="ENABLE_M2M_CHECK"):
        tm.get_dirty_fields(check_m2m=True)


@pytest.mark.django_db
def test_m2m_check_with_custom_primary_key():
    # test for bug: https://github.com/romgar/django-dirtyfields/issues/74
    tm = ModelWithCustomPKTest.objects.create(custom_primary_key="pk1")
    m2m_model = M2MModelWithCustomPKOnM2MTest.objects.create()

    # This line was triggering this error:
    # AttributeError: 'ModelWithCustomPKTest' object has no attribute 'id'
    m2m_model.m2m_field.add(tm)


@pytest.mark.django_db
def test_m2m_disabled_does_not_allow_to_check_m2m_fields():
    tm = ModelWithoutM2MCheckTest.objects.create()

    with pytest.raises(ValueError, match="ENABLE_M2M_CHECK"):
        tm.get_dirty_fields(check_m2m=True)


@pytest.mark.django_db
def test_m2m_is_dirty():
    """Test is_dirty with M2M fields."""
    tm = Many2ManyModelTest.objects.create()
    tm2 = ModelTest.objects.create()

    # First check - not dirty
    assert not tm.is_dirty(check_m2m=True)

    # Add M2M relation - now dirty
    tm.m2m_field.add(tm2)
    assert tm.is_dirty(check_m2m=True)

    # Save - no longer dirty
    tm.save()
    assert not tm.is_dirty(check_m2m=True)
