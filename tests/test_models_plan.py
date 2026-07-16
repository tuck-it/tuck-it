import pytest

from tuckit.core.models import Plan
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_plan_is_one_to_one_with_slice(workspace):
    s = create_slice(create_area(workspace, "B"), "S")
    p = Plan.objects.create(slice=s, body="overview", constraints="no billing")
    assert s.plan == p
    assert p.body == "overview" and p.constraints == "no billing"
    assert p.source == "human"
