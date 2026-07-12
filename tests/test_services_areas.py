import pytest

from tuckit.core.models import Area, Org, Workspace
from tuckit.core.services.areas import create_area, get_or_create_triage, list_areas, rename_area, delete_area, reorder_area
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slices import create_slice


@pytest.fixture
def workspace(db):
    org = Org.objects.create(name="Acme", slug="acme")
    return Workspace.objects.create(org=org, name="P", slug="p")


@pytest.mark.django_db
def test_create_area_autoslug_and_rank(workspace):
    a = create_area(workspace, "Back End")
    assert a.slug == "back-end"
    assert a.rank


@pytest.mark.django_db
def test_areas_are_ordered_by_creation_rank(workspace):
    a = create_area(workspace, "First")
    b = create_area(workspace, "Second")
    assert list(list_areas(workspace)) == [a, b]
    assert a.rank < b.rank


@pytest.mark.django_db
def test_list_areas_excludes_archived_by_default(workspace):
    a = create_area(workspace, "Kept")
    archived = create_area(workspace, "Gone")
    archived.archived = True
    archived.save()
    assert list(list_areas(workspace)) == [a]
    assert archived in list_areas(workspace, include_archived=True)


@pytest.mark.django_db
def test_duplicate_name_gets_unique_slug(workspace):
    a = create_area(workspace, "Backend")
    b = create_area(workspace, "Backend")
    assert a.slug != b.slug


@pytest.mark.django_db
def test_get_or_create_triage_is_idempotent_and_single():
    org = Org.objects.create(name="Acme", slug="acme")
    ws = Workspace.objects.create(org=org, name="W", slug="w")
    a = get_or_create_triage(ws)
    b = get_or_create_triage(ws)
    assert a.id == b.id
    assert a.is_triage is True
    assert Area.objects.filter(workspace=ws, is_triage=True).count() == 1


@pytest.mark.django_db
def test_triage_sorts_before_existing_areas():
    org = Org.objects.create(name="Acme", slug="acme")
    ws = Workspace.objects.create(org=org, name="W", slug="w")
    backend = create_area(ws, "Backend")
    inbox = get_or_create_triage(ws)
    ordered = list(list_areas(ws))
    assert ordered[0].id == inbox.id
    assert ordered[1].id == backend.id


@pytest.mark.django_db
def test_rename_area_changes_name_but_keeps_slug(workspace):
    a = create_area(workspace, "Back End")
    original_slug = a.slug
    renamed = rename_area(a, "Platform")
    a.refresh_from_db()
    assert a.name == "Platform"
    assert a.slug == original_slug
    assert renamed.id == a.id


@pytest.mark.django_db
def test_rename_area_trims_whitespace(workspace):
    a = create_area(workspace, "X")
    rename_area(a, "  Trimmed  ")
    a.refresh_from_db()
    assert a.name == "Trimmed"


@pytest.mark.django_db
def test_rename_area_rejects_blank(workspace):
    a = create_area(workspace, "Keep")
    with pytest.raises(InvalidValue):
        rename_area(a, "   ")
    a.refresh_from_db()
    assert a.name == "Keep"


@pytest.mark.django_db
def test_delete_area_removes_it_and_cascades_slices(workspace):
    a = create_area(workspace, "Doomed")
    create_slice(a, "child idea", status="idea", source="human")
    delete_area(a)
    assert not Area.objects.filter(workspace=workspace, name="Doomed").exists()
    from tuckit.core.models import Slice
    assert not Slice.objects.filter(area_id=a.id).exists()


@pytest.mark.django_db
def test_delete_area_refuses_triage(workspace):
    triage = get_or_create_triage(workspace)
    with pytest.raises(InvalidValue):
        delete_area(triage)
    assert Area.objects.filter(id=triage.id).exists()


@pytest.mark.django_db
def test_reorder_area_moves_before_sibling(workspace):
    a = create_area(workspace, "A")
    b = create_area(workspace, "B")
    c = create_area(workspace, "C")
    # move c before a  ->  C, A, B
    reorder_area(c, before=a)
    ordered = list(list_areas(workspace))
    assert [x.id for x in ordered] == [c.id, a.id, b.id]


@pytest.mark.django_db
def test_reorder_area_moves_after_sibling(workspace):
    a = create_area(workspace, "A")
    b = create_area(workspace, "B")
    c = create_area(workspace, "C")
    # move a after b  ->  B, A, C
    reorder_area(a, after=b)
    ordered = list(list_areas(workspace))
    assert [x.id for x in ordered] == [b.id, a.id, c.id]
