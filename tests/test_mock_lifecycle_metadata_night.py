import pytest
from mockarty.models.mock import Mock

@pytest.mark.parametrize("body,want", [
 ({"id":"deleted","_meta":{"closedAt":1700000000}},1700000000),
 ({"id":"live","_meta":{}},None),
 ({"closedAt":12,"_meta":{"closedAt":20}},12),
 ({"closedAt":0,"_meta":{"closedAt":20}},0),
 ({"closedAt":None,"_meta":{"closedAt":20}},20),
])
def test_night_mock_read_lifecycle_metadata(body,want):
    original=dict(body)
    assert Mock.model_validate(body).closed_at==want
    assert body==original
