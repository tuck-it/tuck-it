import pytest

from tuckit.core.models import Area, Bite, Slice
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_create_first_area(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/area", {"name": "Backend"})
    assert r.status_code == 302
    assert Area.objects.filter(workspace=workspace, is_triage=False, name="Backend").exists()


@pytest.mark.django_db
def test_create_first_slice_targets_the_area(client_local, workspace):
    create_area(workspace, "Backend")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/slice", {"title": "Retry webhooks"})
    assert r.status_code == 302
    assert Slice.objects.filter(area__workspace=workspace, title="Retry webhooks").exists()


@pytest.mark.django_db
def test_create_first_bite_targets_the_slice(client_local, workspace):
    area = create_area(workspace, "Backend")
    create_slice(area, "Retry webhooks", status="idea")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/bite", {"title": "Add backoff"})
    assert r.status_code == 302
    assert Bite.objects.filter(slice__area__workspace=workspace, title="Add backoff").exists()


@pytest.mark.django_db
def test_slice_without_area_is_noop(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/slice", {"title": "Orphan"})
    assert r.status_code == 302
    assert not Slice.objects.filter(area__workspace=workspace).exists()
