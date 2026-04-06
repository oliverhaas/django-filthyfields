import pytest

from tests.models import ModelTest

pytestmark = [pytest.mark.django_db(transaction=True)]


@pytest.mark.asyncio
async def test_asave_resets_dirty_state():
    tm = await ModelTest.objects.acreate()
    assert not tm.is_dirty()

    tm.boolean = False
    assert tm.is_dirty()
    assert tm.get_dirty_fields() == {"boolean": True}

    await tm.asave()
    assert not tm.is_dirty()
    assert tm.get_dirty_fields() == {}


@pytest.mark.asyncio
async def test_asave_captures_was_dirty():
    tm = await ModelTest.objects.acreate(boolean=True, characters="original")

    tm.characters = "modified"
    assert tm.is_dirty()

    await tm.asave()

    assert tm.was_dirty()
    assert tm.get_was_dirty_fields() == {"characters": "original"}
    assert not tm.is_dirty()

    # Save again with no changes
    await tm.asave()
    assert not tm.was_dirty()
    assert tm.get_was_dirty_fields() == {}


@pytest.mark.asyncio
async def test_asave_with_update_fields():
    tm = await ModelTest.objects.acreate(boolean=True, characters="original")

    tm.boolean = False
    tm.characters = "modified"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "original"}

    await tm.asave(update_fields=["boolean"])

    # After partial save, dirty tracking resets ALL fields
    assert not tm.is_dirty()
