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
