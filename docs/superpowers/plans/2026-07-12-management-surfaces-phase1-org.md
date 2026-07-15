# 관리 표면 1단계: 조직 페이지 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/settings/org` 조직 관리 페이지와 그 뒤를 받치는 멤버/조직 서비스 레이어를 추가한다 — 조직 이름 변경, 멤버·역할 보기/변경/제거, 이 조직의 워크스페이스 목록, 조직 삭제(위험구역).

**Architecture:** 서비스 레이어(`core/services/orgs.py`)에 순수 함수로 불변식(최후 owner 보호 등)을 강제하고 `InvalidValue`를 던진다. 얇은 Django 뷰(`web/views/settings_org.py`)가 세션 기반 현재 워크스페이스에서 org를 얻어 authz(`is_org_admin`/`is_org_owner` → 403)를 게이트하고, HTMX 부분 스왑으로 인라인 편집을 처리한다. 템플릿은 기존 `base.html`(Warm Greige) + Alpine + HTMX 패턴을 그대로 따른다.

**Tech Stack:** Django (함수형 뷰 + 서비스 레이어), HTMX 2.x, Alpine.js, pytest + `pytest-django`, uv.

## Global Constraints

- 공개 레포 `tuckit`(BSL 1.1). **billing/Paddle/가격/플랜 이름/업그레이드 문구를 이 레포에 절대 넣지 않는다.** 조직 페이지의 플랜 영역은 빈 중립 슬롯(`{% block org_plan %}{% endblock %}`)만 둔다.
- 커스텀 유저 모델 `core.User`, 테넌시: `User ─OrgMember(role)─ Org ─< Workspace ─< Area`.
- 역할: `owner` / `admin` / `member` (`OrgMember.ROLE_CHOICES`).
- 권한: 조직 이름변경·멤버제거·워크스페이스 = admin+; 역할변경·조직삭제 = owner.
- 서비스는 authz를 하지 않는다(뷰가 함). 서비스는 **데이터 불변식**만 강제하고 `tuckit.core.services.exceptions.InvalidValue`를 던진다.
- 테스트: `uv run pytest`. 모든 DB 테스트에 `@pytest.mark.django_db`. 커밋은 자주.
- Warm Greige 팔레트/토큰만 사용(`tokens.css`), 새 색 발명 금지.
- 이 문서와 스펙은 `docs/superpowers/`(gitignore됨) — **커밋하지 않는다.** (플랜 자체는 add 하지 말 것.)

---

## File Structure

- `tuckit/core/services/orgs.py` (수정) — 멤버/조직 서비스 추가: `is_org_owner`, `rename_org`, `list_org_members`, `change_member_role`, `remove_member`.
- `tuckit/web/views/settings_org.py` (신규) — `org_settings`(GET), `org_rename`, `member_role`, `member_remove`, `org_delete`.
- `tuckit/web/urls.py` (수정) — `/settings/org` 및 하위 POST 라우트 5개.
- `tuckit/web/templates/web/settings_org.html` (신규) — 조직 페이지.
- `tuckit/web/templates/web/partials/_member_row.html` (신규) — 멤버 행(역할 select + 제거), HTMX 스왑 대상.
- `tuckit/web/templates/web/partials/_settings_scopenav.html` (신규) — 계정/조직/워크스페이스 스코프 탭(공유).
- `tests/test_services_orgs.py` (수정) — 서비스 테스트 추가.
- `tests/web/test_settings_org.py` (신규) — 뷰 테스트.

각 태스크는 실패 테스트 → 실행(실패 확인) → 최소 구현 → 실행(통과) → 커밋 사이클을 가진다.

---

### Task 1: 멤버/조직 서비스 레이어

**Files:**
- Modify: `tuckit/core/services/orgs.py`
- Test: `tests/test_services_orgs.py`

**Interfaces:**
- Consumes: `tuckit.core.models.{Org, OrgMember}`, `tuckit.core.services.exceptions.InvalidValue`.
- Produces:
  - `is_org_owner(user, org) -> bool`
  - `rename_org(org, name: str) -> Org` — 빈 이름이면 `InvalidValue`.
  - `list_org_members(org) -> QuerySet[OrgMember]` — `select_related("user")`, 가입순.
  - `change_member_role(org, *, member: OrgMember, role: str) -> OrgMember` — `role`이 `owner/admin/member` 밖이거나 마지막 owner를 강등하면 `InvalidValue`.
  - `remove_member(org, *, member: OrgMember) -> None` — `member.role == "owner"`면 `InvalidValue`(owner는 먼저 강등).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_services_orgs.py` 하단에 추가(파일 상단 import에 아래 이름을 더한다):

```python
# --- add to the existing top-of-file import block ---
from tuckit.core.services.orgs import (
    is_org_owner, rename_org, list_org_members, change_member_role, remove_member,
)
from tuckit.core.services.exceptions import InvalidValue


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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_services_orgs.py -q`
Expected: FAIL — `ImportError: cannot import name 'is_org_owner'` (등).

- [ ] **Step 3: 최소 구현**

`tuckit/core/services/orgs.py` 상단 import에 `InvalidValue`를 추가하고 파일 끝에 함수들을 추가:

```python
# top of file — extend the existing import
from tuckit.core.services.exceptions import InvalidValue

_VALID_ROLES = {"owner", "admin", "member"}


def is_org_owner(user, org) -> bool:
    return OrgMember.objects.filter(user=user, org=org, role="owner").exists()


def rename_org(org: Org, name: str) -> Org:
    name = (name or "").strip()
    if not name:
        raise InvalidValue("조직 이름을 입력하세요")
    org.name = name
    org.save(update_fields=["name"])
    return org


def list_org_members(org: Org):
    return OrgMember.objects.filter(org=org).select_related("user").order_by("created_at")


def _owner_count(org: Org) -> int:
    return OrgMember.objects.filter(org=org, role="owner").count()


def change_member_role(org: Org, *, member: OrgMember, role: str) -> OrgMember:
    if role not in _VALID_ROLES:
        raise InvalidValue(f"알 수 없는 역할: {role}")
    if member.role == "owner" and role != "owner" and _owner_count(org) <= 1:
        raise InvalidValue("마지막 소유자의 역할은 바꿀 수 없습니다")
    member.role = role
    member.save(update_fields=["role"])
    return member


def remove_member(org: Org, *, member: OrgMember) -> None:
    if member.role == "owner":
        raise InvalidValue("소유자는 제거할 수 없습니다 — 먼저 역할을 변경하세요")
    member.delete()
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_services_orgs.py -q`
Expected: PASS (신규 + 기존 테스트 모두).

- [ ] **Step 5: 커밋**

```bash
git add tuckit/core/services/orgs.py tests/test_services_orgs.py
git commit -m "feat(core): org member management services (rename, roles, remove)"
```

---

### Task 2: `/settings/org` 페이지 렌더 (GET)

**Files:**
- Create: `tuckit/web/views/settings_org.py`
- Create: `tuckit/web/templates/web/settings_org.html`
- Create: `tuckit/web/templates/web/partials/_settings_scopenav.html`
- Create: `tuckit/web/templates/web/partials/_member_row.html`
- Modify: `tuckit/web/urls.py`
- Test: `tests/web/test_settings_org.py`

**Interfaces:**
- Consumes: `list_org_members`, `is_org_admin`, `is_org_owner` (Task 1), `get_current_workspace` (`tuckit.web.auth`).
- Produces: URL name `web:settings_org` at path `settings/org`; template context `{workspace, org, members, workspaces, can_admin, can_owner}`.

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_org.py`:

```python
import pytest

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.orgs import create_workspace


def _login(client, user, ws):
    client.force_login(user)
    session = client.session
    session["active_workspace_id"] = ws.id
    session.save()


@pytest.fixture
def org_ctx(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(username="o@a.com", email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    member = User.objects.create(username="m@a.com", email="m@a.com")
    OrgMember.objects.create(user=member, org=org, role="member")
    ws = create_workspace(org, "Board")
    return client, org, owner, member, ws


@pytest.mark.django_db
def test_org_page_lists_members_and_workspaces(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    resp = client.get("/settings/org")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Acme" in body
    assert "o@a.com" in body and "m@a.com" in body
    assert "Board" in body


@pytest.mark.django_db
def test_org_page_requires_login(client, db):
    resp = client.get("/settings/org")
    assert resp.status_code in (302, 403)
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_org.py -q`
Expected: FAIL — 404 (라우트 없음).

- [ ] **Step 3: 뷰 구현**

`tuckit/web/views/settings_org.py`:

```python
from django.shortcuts import render

from tuckit.core.services.orgs import is_org_admin, is_org_owner, list_org_members
from tuckit.web.auth import get_current_workspace


def org_settings(request):
    ws = get_current_workspace(request)
    org = ws.org if ws else None
    members = list(list_org_members(org)) if org else []
    workspaces = list(org.workspaces.order_by("name")) if org else []
    return render(request, "web/settings_org.html", {
        "workspace": ws,
        "org": org,
        "members": members,
        "workspaces": workspaces,
        "can_admin": bool(org and is_org_admin(request.user, org)),
        "can_owner": bool(org and is_org_owner(request.user, org)),
    })
```

- [ ] **Step 4: 라우트 추가**

`tuckit/web/urls.py`의 import 줄에 `settings_org`를 더하고 urlpatterns에 라우트를 추가:

```python
# import line — add settings_org
from tuckit.web.views import pages, slices, mutations, board, capture, health, workspaces, accounts, settings_org
# ... in urlpatterns, near the other settings/ routes:
    path("settings/org", settings_org.org_settings, name="settings_org"),
```

- [ ] **Step 5: 스코프 내비 partial**

`tuckit/web/templates/web/partials/_settings_scopenav.html`:

```django
<div class="scopenav">
  <a class="scope {% if active == 'org' %}on{% endif %}" href="{% url 'web:settings_org' %}">조직{% if org %} · {{ org.name }}{% endif %}</a>
  <a class="scope {% if active == 'workspace' %}on{% endif %}" href="{% url 'web:settings' %}">워크스페이스{% if workspace %} · {{ workspace.name }}{% endif %}</a>
</div>
```

- [ ] **Step 6: 멤버 행 partial**

`tuckit/web/templates/web/partials/_member_row.html`:

```django
<div class="field member-row" id="member-{{ m.id }}">
  <div class="row-l">
    <span class="avatar">{{ m.user.email|slice:":1"|upper }}</span>
    <div><div class="nm">{{ m.user.email }}</div>{% if m.user == request.user %}<div class="sub">나</div>{% endif %}</div>
  </div>
  <div class="row-l" style="gap:8px">
    {% if can_owner and m.user != request.user %}
      <select hx-post="{% url 'web:org_member_role' m.id %}" hx-swap="none" name="role">
        {% for value, label in role_choices %}
          <option value="{{ value }}" {% if m.role == value %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>
    {% else %}
      <span class="rolepill">{{ m.get_role_display }}</span>
    {% endif %}
    {% if can_admin and m.role != 'owner' and m.user != request.user %}
      <button class="btn" hx-post="{% url 'web:org_member_remove' m.id %}"
              hx-target="#member-{{ m.id }}" hx-swap="outerHTML" hx-confirm="이 멤버를 제거할까요?">제거</button>
    {% endif %}
  </div>
</div>
```

- [ ] **Step 7: 조직 페이지 템플릿**

`tuckit/web/templates/web/settings_org.html`:

```django
{% extends "web/base.html" %}
{% block main %}
  {% include "web/partials/_settings_scopenav.html" with active='org' %}
  <div class="topbar"><h1 class="area-title">조직 설정</h1></div>
  <div class="empty muted">멤버와 플랜은 조직 단위로 관리됩니다.</div>

  <section class="group">
    <div class="group-label">조직 이름</div>
    <div class="settings-name" x-data="{editing:false, name:'{{ org.name|escapejs }}'}">
      <span class="settings-name-display" x-show="!editing" x-on:click="editing = can_admin" x-text="name"></span>
      {% if can_admin %}
      <input name="name" class="title-edit" x-show="editing" x-cloak x-model="name"
             hx-post="{% url 'web:org_rename' %}" hx-trigger="blur, keydown[key=='Enter']"
             hx-vals="js:{name: name}" hx-swap="none"
             x-on:keydown.enter="editing=false" x-on:blur="editing=false">
      {% endif %}
    </div>
  </section>

  {% block org_plan %}{% endblock %}{# neutral slot — cloud fills plan/billing here #}

  <section class="group">
    <div class="group-label">멤버 · 역할</div>
    <div id="members-list" class="panel">
      {% for m in members %}{% include "web/partials/_member_row.html" %}{% endfor %}
    </div>
  </section>

  <section class="group">
    <div class="group-label">이 조직의 워크스페이스</div>
    <div class="panel">
      {% for ws in workspaces %}
        <div class="field"><span class="nm">{{ ws.name }}</span></div>
      {% endfor %}
    </div>
  </section>

  {% if can_owner %}
  <section class="group">
    <div class="group-label danger">위험 구역</div>
    <form hx-post="{% url 'web:org_delete' %}" hx-confirm="조직과 모든 워크스페이스가 삭제됩니다. 계속할까요?">
      <button type="submit" class="btn danger">조직 삭제</button>
    </form>
  </section>
  {% endif %}
{% endblock %}
```

- [ ] **Step 8: 뷰 컨텍스트에 role_choices/can_* 노출 확인 및 통과**

`_member_row.html`이 `role_choices`·`can_owner`·`can_admin`을 참조하므로 `org_settings` 컨텍스트에 `role_choices`를 추가한다(뷰 수정):

```python
from tuckit.core.models import OrgMember
# ... in the render context dict, add:
        "role_choices": OrgMember.ROLE_CHOICES,
```

Run: `uv run pytest tests/web/test_settings_org.py -q`
Expected: PASS.

- [ ] **Step 9: 커밋**

```bash
git add tuckit/web/views/settings_org.py tuckit/web/urls.py tuckit/web/templates/web/settings_org.html tuckit/web/templates/web/partials/_settings_scopenav.html tuckit/web/templates/web/partials/_member_row.html tests/web/test_settings_org.py
git commit -m "feat(web): /settings/org page listing members and workspaces"
```

---

### Task 3: 조직 이름 변경 (POST, 인라인)

**Files:**
- Modify: `tuckit/web/views/settings_org.py`
- Modify: `tuckit/web/urls.py`
- Test: `tests/web/test_settings_org.py`

**Interfaces:**
- Consumes: `rename_org`, `is_org_admin` (Task 1).
- Produces: URL name `web:org_rename` at `settings/org/rename` (POST).

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_org.py`에 추가:

```python
@pytest.mark.django_db
def test_owner_renames_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    resp = client.post("/settings/org/rename", {"name": "Beta"})
    assert resp.status_code == 200
    org.refresh_from_db()
    assert org.name == "Beta"


@pytest.mark.django_db
def test_member_cannot_rename_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, member, ws)
    resp = client.post("/settings/org/rename", {"name": "Beta"})
    assert resp.status_code == 403
    org.refresh_from_db()
    assert org.name == "Acme"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_org.py -k rename -q`
Expected: FAIL — 404.

- [ ] **Step 3: 뷰 구현**

`settings_org.py`에 추가:

```python
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST

from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.orgs import rename_org


@require_POST
def org_rename(request):
    ws = get_current_workspace(request)
    if ws is None or not is_org_admin(request.user, ws.org):
        return HttpResponseForbidden("권한이 없습니다")
    try:
        org = rename_org(ws.org, request.POST.get("name", ""))
    except InvalidValue as exc:
        return HttpResponse(str(exc), status=400)
    return HttpResponse(org.name)
```

- [ ] **Step 4: 라우트 추가**

`urls.py`에 추가:

```python
    path("settings/org/rename", settings_org.org_rename, name="org_rename"),
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/web/test_settings_org.py -k rename -q`
Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
git add tuckit/web/views/settings_org.py tuckit/web/urls.py tests/web/test_settings_org.py
git commit -m "feat(web): rename org from /settings/org"
```

---

### Task 4: 멤버 역할 변경 · 제거 (POST, HTMX)

**Files:**
- Modify: `tuckit/web/views/settings_org.py`
- Modify: `tuckit/web/urls.py`
- Test: `tests/web/test_settings_org.py`

**Interfaces:**
- Consumes: `change_member_role`, `remove_member`, `is_org_owner`, `is_org_admin` (Task 1); partial `_member_row.html` (Task 2).
- Produces: URL names `web:org_member_role` (`settings/org/members/<int:member_id>/role`, POST) 및 `web:org_member_remove` (`settings/org/members/<int:member_id>/remove`, POST).

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_org.py`에 추가:

```python
from tuckit.core.models import OrgMember


@pytest.mark.django_db
def test_owner_changes_member_role(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    om = OrgMember.objects.get(org=org, user=member)
    resp = client.post(f"/settings/org/members/{om.id}/role", {"role": "admin"})
    assert resp.status_code == 200
    om.refresh_from_db()
    assert om.role == "admin"


@pytest.mark.django_db
def test_admin_cannot_change_role(org_ctx):
    client, org, owner, member, ws = org_ctx
    # promote member to admin first (as owner), then act as that admin
    OrgMember.objects.filter(org=org, user=member).update(role="admin")
    _login(client, member, ws)
    om_owner = OrgMember.objects.get(org=org, user=owner)
    resp = client.post(f"/settings/org/members/{om_owner.id}/role", {"role": "member"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_removes_member(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    om = OrgMember.objects.get(org=org, user=member)
    resp = client.post(f"/settings/org/members/{om.id}/remove")
    assert resp.status_code == 204
    assert not OrgMember.objects.filter(id=om.id).exists()


@pytest.mark.django_db
def test_cannot_remove_member_of_other_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    other = Org.objects.create(name="Other", slug="other")
    stranger = User.objects.create(username="s@s.com", email="s@s.com")
    om_other = OrgMember.objects.create(user=stranger, org=other, role="member")
    _login(client, owner, ws)
    resp = client.post(f"/settings/org/members/{om_other.id}/remove")
    assert resp.status_code == 404
    assert OrgMember.objects.filter(id=om_other.id).exists()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_org.py -k "role or remove" -q`
Expected: FAIL — 404.

- [ ] **Step 3: 뷰 구현**

`settings_org.py`에 추가:

```python
from django.http import Http404
from django.shortcuts import get_object_or_404

from tuckit.core.models import OrgMember
from tuckit.core.services.orgs import change_member_role, remove_member


def _member_in_current_org(request, member_id):
    """Fetch an OrgMember, 404 unless it belongs to the caller's current org."""
    ws = get_current_workspace(request)
    if ws is None:
        raise Http404
    return ws, get_object_or_404(OrgMember, id=member_id, org=ws.org)


@require_POST
def member_role(request, member_id):
    ws, member = _member_in_current_org(request, member_id)
    if not is_org_owner(request.user, ws.org):
        return HttpResponseForbidden("권한이 없습니다")
    try:
        change_member_role(ws.org, member=member, role=request.POST.get("role", ""))
    except InvalidValue as exc:
        return HttpResponse(str(exc), status=400)
    return render(request, "web/partials/_member_row.html", {
        "m": member, "role_choices": OrgMember.ROLE_CHOICES,
        "can_owner": True, "can_admin": True,
    })


@require_POST
def member_remove(request, member_id):
    ws, member = _member_in_current_org(request, member_id)
    if not is_org_admin(request.user, ws.org):
        return HttpResponseForbidden("권한이 없습니다")
    try:
        remove_member(ws.org, member=member)
    except InvalidValue as exc:
        return HttpResponse(str(exc), status=400)
    return HttpResponse(status=204)
```

- [ ] **Step 4: 라우트 추가**

`urls.py`에 추가:

```python
    path("settings/org/members/<int:member_id>/role", settings_org.member_role, name="org_member_role"),
    path("settings/org/members/<int:member_id>/remove", settings_org.member_remove, name="org_member_remove"),
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/web/test_settings_org.py -k "role or remove" -q`
Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
git add tuckit/web/views/settings_org.py tuckit/web/urls.py tests/web/test_settings_org.py
git commit -m "feat(web): change member role and remove member (org owner/admin)"
```

---

### Task 5: 조직 삭제 (위험 구역, 마지막 조직 보호)

**Files:**
- Modify: `tuckit/web/views/settings_org.py`
- Modify: `tuckit/web/urls.py`
- Test: `tests/web/test_settings_org.py`

**Interfaces:**
- Consumes: `is_org_owner` (Task 1); `OrgMember` 모델.
- Produces: URL name `web:org_delete` at `settings/org/delete` (POST). 성공 시 세션 `active_workspace_id` 정리 후 `/`로 리다이렉트(다른 조직으로 폴백). 마지막 조직이면 400.

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_org.py`에 추가:

```python
from tuckit.core.models import Org as OrgModel  # alias to avoid fixture shadow


@pytest.mark.django_db
def test_owner_deletes_org_when_has_another(org_ctx):
    client, org, owner, member, ws = org_ctx
    # owner also belongs to a second org, so deleting the first is allowed
    other = OrgModel.objects.create(name="Personal", slug="personal")
    OrgMember.objects.create(user=owner, org=other, role="owner")
    create_workspace(other, "Home")
    _login(client, owner, ws)
    resp = client.post("/settings/org/delete")
    assert resp.status_code == 302
    assert not OrgModel.objects.filter(id=org.id).exists()


@pytest.mark.django_db
def test_cannot_delete_last_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    resp = client.post("/settings/org/delete")
    assert resp.status_code == 400
    assert OrgModel.objects.filter(id=org.id).exists()


@pytest.mark.django_db
def test_member_cannot_delete_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, member, ws)
    resp = client.post("/settings/org/delete")
    assert resp.status_code == 403
    assert OrgModel.objects.filter(id=org.id).exists()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_org.py -k delete -q`
Expected: FAIL — 404.

- [ ] **Step 3: 뷰 구현**

`settings_org.py`에 추가:

```python
from django.shortcuts import redirect


@require_POST
def org_delete(request):
    ws = get_current_workspace(request)
    if ws is None or not is_org_owner(request.user, ws.org):
        return HttpResponseForbidden("권한이 없습니다")
    org = ws.org
    has_other = OrgMember.objects.filter(user=request.user).exclude(org=org).exists()
    if not has_other:
        return HttpResponse("마지막 조직은 삭제할 수 없습니다", status=400)
    request.session.pop("active_workspace_id", None)
    org.delete()  # cascades to workspaces/areas/slices/bites via FK on_delete=CASCADE
    return redirect("web:home")
```

- [ ] **Step 4: 라우트 추가**

`urls.py`에 추가:

```python
    path("settings/org/delete", settings_org.org_delete, name="org_delete"),
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/web/test_settings_org.py -q`
Expected: PASS (Task 2–5 전체).

- [ ] **Step 6: 전체 스위트 회귀 확인 후 커밋**

Run: `uv run pytest -q`
Expected: PASS (기존 테스트 무회귀).

```bash
git add tuckit/web/views/settings_org.py tuckit/web/urls.py tests/web/test_settings_org.py
git commit -m "feat(web): delete org from danger zone (owner-only, last-org guard)"
```

---

## Self-Review (작성자 체크)

- **스펙 커버리지(1단계 한정):** 조직 이름변경(Task 3) · 멤버 목록/역할변경/제거(Task 1·2·4) · 워크스페이스 목록(Task 2) · 위험구역 삭제(Task 5) · 중립 플랜 슬롯 `{% block org_plan %}`(Task 2) · 스코프 내비(Task 2). 초대 생성/취소는 기존 `/settings/invites`가 이미 처리하므로 1단계에서 재구현하지 않고, 후속에서 조직 페이지로 이관. ✓
- **1단계 밖(후속 계획):** 워크스페이스 페이지/삭제(2단계), Area 인라인 CRUD(3단계), 계정 페이지·`list_user_orgs`·`create_org`·`leave_org`·조직 전환기(4단계), cloud 플랜 슬롯 연결(5단계), `/settings/` → `/settings/workspace` 리다이렉트 및 계정 스코프 탭 링크(2·4단계).
- **플레이스홀더 스캔:** 모든 스텝에 실제 코드/명령/기대출력 포함. 없음. ✓
- **타입 일관성:** 서비스 시그니처(`change_member_role(org, *, member, role)` 등)가 뷰 호출부와 일치. partial `_member_row.html`이 참조하는 `m`·`role_choices`·`can_owner`·`can_admin`을 Task 2 Step 8 및 Task 4 렌더 컨텍스트에서 모두 제공. ✓
- **주의:** `_member_row.html`의 `hx-post` select는 `hx-swap="none"`(값 갱신만); 실패 시 400 메시지는 Task 4에서 반환하나 UI 표면화는 후속 폴리시. 1단계 수용.
```
