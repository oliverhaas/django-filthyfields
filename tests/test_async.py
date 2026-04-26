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

    # `boolean` was persisted — clean. `characters` was not — still dirty.
    assert tm.get_dirty_fields() == {"characters": "original"}


@pytest.mark.asyncio
async def test_arefresh_from_db_resets_dirty_state():
    tm = await ModelTest.objects.acreate(boolean=True, characters="original")
    alias = await ModelTest.objects.aget(pk=tm.pk)
    alias.boolean = False
    await alias.asave()

    # tm still has stale local state
    assert tm.boolean is True

    await tm.arefresh_from_db()
    assert tm.boolean is False
    assert tm.get_dirty_fields() == {}


@pytest.mark.asyncio
async def test_arefresh_from_db_partial_fields():
    tm = await ModelTest.objects.acreate(characters="old value")
    tm.boolean = False
    tm.characters = "new value"
    assert tm.get_dirty_fields() == {"boolean": True, "characters": "old value"}

    await tm.arefresh_from_db(fields=["characters"])
    assert tm.boolean is False
    assert tm.characters == "old value"
    assert tm.get_dirty_fields() == {"boolean": True}


@pytest.mark.asyncio
async def test_aget_produces_clean_state():
    created = await ModelTest.objects.acreate(boolean=True, characters="hello")
    tm = await ModelTest.objects.aget(pk=created.pk)

    assert not tm.is_dirty()
    assert tm.get_dirty_fields() == {}


@pytest.mark.asyncio
async def test_arefresh_from_db_with_from_queryset():
    """arefresh_from_db(from_queryset=...) resets dirty state, mirroring sync version."""
    tm = await ModelTest.objects.acreate(boolean=True, characters="initial")
    alias = await ModelTest.objects.aget(pk=tm.pk)
    alias.characters = "updated"
    await alias.asave()

    tm.boolean = False
    assert tm.get_dirty_fields() == {"boolean": True}

    await tm.arefresh_from_db(from_queryset=ModelTest.objects.all())
    assert tm.characters == "updated"
    assert tm.get_dirty_fields() == {}
