import pytest

from tuckit.core.models import Area, Org, OrgMember, User, Workspace
from tuckit.core.services.orgs import (
    accessible_workspaces, user_can_access_workspace, is_org_admin, seat_count, create_workspace,
    is_org_owner, rename_org, list_org_members, change_member_role, remove_member, delete_workspace,
)
from tuckit.core.services.exceptions import InvalidValue


@pytest.fixture
def org_with_owner(db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create(username="o@a.com", email="o@a.com")
    OrgMember.objects.create(user=user, org=org, role="owner")
    return org, user


@pytest.mark.django_db
def test_create_workspace_sets_up_inbox_and_default(org_with_owner):
    org, _ = org_with_owner
    ws = create_workspace(org, "Board")
    assert ws.org == org
    assert Area.objects.filter(workspace=ws, is_triage=True).count() == 1
    assert Area.objects.filter(workspace=ws, is_triage=False, slug="default").exists()


@pytest.mark.django_db
def test_create_workspace_unique_slug_within_org(org_with_owner):
    org, _ = org_with_owner
    a = create_workspace(org, "Board")
    b = create_workspace(org, "Board")
    assert a.slug != b.slug


@pytest.mark.django_db
def test_access_helpers(org_with_owner):
    org, user = org_with_owner
    ws = create_workspace(org, "Board")
    assert user_can_access_workspace(user, ws) is True
    assert is_org_admin(user, org) is True
    assert seat_count(org) == 1

    outsider = User.objects.create(username="x@x.com", email="x@x.com")
    assert user_can_access_workspace(outsider, ws) is False
    assert is_org_admin(outsider, org) is False
    assert list(accessible_workspaces(user)) == [ws]
    assert list(accessible_workspaces(outsider)) == []


@pytest.fixture
def org_owner_admin_member(db):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(username="owner@a.com", email="owner@a.com")
    admin = User.objects.create(username="admin@a.com", email="admin@a.com")
    member = User.objects.create(username="member@a.com", email="member@a.com")
    om_owner = OrgMember.objects.create(user=owner, org=org, role="owner")
    om_admin = OrgMember.objects.create(user=admin, org=org, role="admin")
    om_member = OrgMember.objects.create(user=member, org=org, role="member")
    return org, om_owner, om_admin, om_member


@pytest.mark.django_db
def test_is_org_owner(org_owner_admin_member):
    org, om_owner, om_admin, _ = org_owner_admin_member
    assert is_org_owner(om_owner.user, org) is True
    assert is_org_owner(om_admin.user, org) is False


@pytest.mark.django_db
def test_rename_org(org_with_owner):
    org, _ = org_with_owner
    rename_org(org, "Beta")
    org.refresh_from_db()
    assert org.name == "Beta"


@pytest.mark.django_db
def test_rename_org_rejects_blank(org_with_owner):
    org, _ = org_with_owner
    with pytest.raises(InvalidValue):
        rename_org(org, "   ")


@pytest.mark.django_db
def test_list_org_members_ordered(org_owner_admin_member):
    org, om_owner, om_admin, om_member = org_owner_admin_member
    assert list(list_org_members(org)) == [om_owner, om_admin, om_member]


@pytest.mark.django_db
def test_change_member_role(org_owner_admin_member):
    org, _, om_admin, _ = org_owner_admin_member
    change_member_role(org, member=om_admin, role="member")
    om_admin.refresh_from_db()
    assert om_admin.role == "member"


@pytest.mark.django_db
def test_change_member_role_rejects_bad_role(org_owner_admin_member):
    org, _, om_admin, _ = org_owner_admin_member
    with pytest.raises(InvalidValue):
        change_member_role(org, member=om_admin, role="superadmin")


@pytest.mark.django_db
def test_cannot_demote_last_owner(org_with_owner):
    org, owner = org_with_owner
    om = OrgMember.objects.get(org=org, user=owner)
    with pytest.raises(InvalidValue):
        change_member_role(org, member=om, role="admin")


@pytest.mark.django_db
def test_remove_member(org_owner_admin_member):
    org, _, _, om_member = org_owner_admin_member
    remove_member(org, member=om_member)
    assert not OrgMember.objects.filter(id=om_member.id).exists()


@pytest.mark.django_db
def test_cannot_remove_owner(org_owner_admin_member):
    org, om_owner, _, _ = org_owner_admin_member
    with pytest.raises(InvalidValue):
        remove_member(org, member=om_owner)


@pytest.mark.django_db
def test_delete_workspace_removes_it_and_cascades(org_with_owner):
    org, _ = org_with_owner
    keep = create_workspace(org, "Keep")
    doomed = create_workspace(org, "Doomed")
    area_ids = list(Area.objects.filter(workspace=doomed).values_list("id", flat=True))
    assert area_ids  # create_workspace seeds inbox + Default
    delete_workspace(doomed)
    assert not Workspace.objects.filter(id=doomed.id).exists()
    assert not Area.objects.filter(id__in=area_ids).exists()  # cascaded
    assert Workspace.objects.filter(id=keep.id).exists()


@pytest.mark.django_db
def test_cannot_delete_last_workspace_in_org(org_with_owner):
    org, _ = org_with_owner
    only = create_workspace(org, "Only")
    with pytest.raises(InvalidValue):
        delete_workspace(only)
    assert Workspace.objects.filter(id=only.id).exists()
