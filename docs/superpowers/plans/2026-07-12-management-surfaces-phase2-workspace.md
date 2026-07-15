# 관리 표면 2단계: 워크스페이스 페이지 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 옛 `/settings/` 잡탕을 `/settings/workspace` 전용 페이지로 분리하고(이름·토큰·에이전트·삭제), 워크스페이스 삭제를 추가하며, 멤버 초대 UI를 조직 페이지(`/settings/org`)로 이관한다.

**Architecture:** 1단계에서 만든 스코프 라우트/담김 IA를 이어간다. 데이터 불변식(마지막 워크스페이스 보호)은 서비스 레이어(`orgs.py`)가 `InvalidValue`로 강제하고, 얇은 뷰가 authz(admin+ → 403)를 게이트한다. 옛 `/settings/`는 `/settings/workspace`로 302 리다이렉트해 하위호환을 지킨다. 템플릿은 기존 Warm Greige + HTMX + Alpine 패턴을 그대로 따른다.

**Tech Stack:** Django (함수형 뷰 + 서비스 레이어), HTMX 2.x, Alpine.js, pytest + pytest-django, uv.

## Global Constraints

- 공개 레포 `tuckit`(BSL 1.1). **billing/Paddle/가격/플랜/업그레이드 문구 금지.**
- 테넌시: `User ─OrgMember(role)─ Org ─< Workspace ─< Area`. 역할 `owner/admin/member`.
- 권한: 워크스페이스 삭제 = admin+ (`is_org_admin`). 멤버·초대·플랜은 **조직 레벨**(워크스페이스 페이지엔 멤버/초대 없음 — 링크만).
- 서비스는 authz를 하지 않음. 데이터 불변식만 강제하고 `tuckit.core.services.exceptions.InvalidValue`를 던짐. 뷰가 authz(403)를 함.
- 세션 기반 "현재 워크스페이스"(`get_current_workspace`). 슬러그 URL 아님.
- Warm Greige 토큰만(`tokens.css`), 새 색 발명 금지. 기존 CSS 클래스(`group/group-label/panel/field/btn/danger/settings-name/title-edit/empty/muted/topbar/area-title/token-add`) 재사용.
- 테스트: `uv run pytest`. 모든 DB 테스트 `@pytest.mark.django_db`. 커밋 자주.
- 이 문서·스펙은 `docs/superpowers/`(gitignore됨) — **커밋하지 않는다.**

## 현재 상태(1단계 병합 후, main=fc4d6b4)

- `/settings/`(name `settings`) → `settings_views.settings` → `settings.html`: 워크스페이스 이름 + 토큰 + **초대** + MCP.
- `settings.py` 뷰: `settings`(GET), `token_create`, `token_revoke`, `workspace_rename`, `invite_create`, `invite_cancel`.
- `_settings_scopenav.html`: 워크스페이스 링크 → `web:settings`. `_sidebar.html` ⚙ 설정 → `web:settings`(active 검사 `url_name == 'settings'`).
- `settings_org.html`(1단계): 이름·플랜 슬롯·멤버·워크스페이스 목록·위험구역. **초대 UI 없음.**
- 파셜: `_token_row.html`, `_invite_row.html` 존재.
- `orgs.py`: `create_workspace`, `is_org_admin`, `is_org_owner`, `seat_count` 등.

## File Structure

- `tuckit/core/services/orgs.py` (수정) — `delete_workspace(workspace)` 추가.
- `tuckit/web/views/settings.py` (수정) — `workspace_settings`(GET) 추가; `settings`를 리다이렉트로 변경; `workspace_delete`(POST) 추가. 기존 토큰/rename/invite 뷰 유지.
- `tuckit/web/templates/web/settings_workspace.html` (신규) — 워크스페이스 페이지.
- `tuckit/web/templates/web/settings.html` (삭제) — 내용이 settings_workspace.html로 이관됨(초대 제외). *실제로는 Task 2에서 신규 템플릿을 만들고 이 파일은 더 이상 렌더되지 않으므로 삭제한다.*
- `tuckit/web/templates/web/settings_org.html` (수정) — 멤버 초대 섹션 추가.
- `tuckit/web/templates/web/partials/_settings_scopenav.html` (수정) — 워크스페이스 링크를 `settings_workspace`로.
- `tuckit/web/templates/web/partials/_sidebar.html` (수정) — ⚙ 설정 링크/active를 `settings_workspace`로.
- `tuckit/web/views/settings_org.py` (수정) — `org_settings` 컨텍스트에 `invitations` 추가.
- `tuckit/web/urls.py` (수정) — `settings/workspace`, `settings/workspace/delete` 라우트 추가.
- `tests/test_services_orgs.py` (수정), `tests/web/test_settings_workspace.py` (신규), `tests/web/test_settings.py` (수정), `tests/web/test_settings_org.py` (수정).

---

### Task 1: `delete_workspace` 서비스

**Files:**
- Modify: `tuckit/core/services/orgs.py`
- Test: `tests/test_services_orgs.py`

**Interfaces:**
- Consumes: `tuckit.core.models.Workspace`, `InvalidValue`.
- Produces: `delete_workspace(workspace: Workspace) -> None` — 그 워크스페이스가 조직의 **유일한** 워크스페이스면 `InvalidValue`; 아니면 삭제(FK on_delete=CASCADE로 area/slice/bite까지 제거).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_services_orgs.py` 하단에 추가(파일 상단 import에 `delete_workspace`, `Area`를 반영 — `Area`는 이미 import되어 있고, `orgs` import 그룹에 `delete_workspace`를 더한다):

```python
from tuckit.core.services.orgs import delete_workspace  # add to existing orgs import group


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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_services_orgs.py -k workspace -q`
Expected: FAIL — `ImportError: cannot import name 'delete_workspace'`.

- [ ] **Step 3: 최소 구현**

`tuckit/core/services/orgs.py` 끝에 추가:

```python
def delete_workspace(workspace: Workspace) -> None:
    if Workspace.objects.filter(org=workspace.org).count() <= 1:
        raise InvalidValue("조직의 마지막 워크스페이스는 삭제할 수 없습니다")
    workspace.delete()
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_services_orgs.py -q`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add tuckit/core/services/orgs.py tests/test_services_orgs.py
git commit -m "feat(core): delete_workspace service with last-workspace guard"
```

---

### Task 2: `/settings/workspace` 페이지 + `/settings/` 리다이렉트 + 내비 재지정

**Files:**
- Modify: `tuckit/web/views/settings.py`
- Create: `tuckit/web/templates/web/settings_workspace.html`
- Delete: `tuckit/web/templates/web/settings.html`
- Modify: `tuckit/web/urls.py`
- Modify: `tuckit/web/templates/web/partials/_settings_scopenav.html`
- Modify: `tuckit/web/templates/web/partials/_sidebar.html`
- Test: `tests/web/test_settings_workspace.py`, `tests/web/test_settings.py`

**Interfaces:**
- Consumes: `list_tokens` (`tokens.py`), `is_org_admin` (`orgs.py`), `get_current_workspace`.
- Produces: URL names `web:settings_workspace` (`settings/workspace`, GET) 및 유지되는 `web:settings`(이제 302 → settings_workspace). 컨텍스트 `{workspace, org, tokens, mcp_url, can_admin}`.

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_workspace.py`:

```python
import pytest


@pytest.mark.django_db
def test_workspace_page_renders(client_local, workspace):
    from tuckit.core.services.tokens import generate_token
    generate_token(workspace, "Existing")
    resp = client_local.get("/settings/workspace")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert workspace.name in body        # rename field
    assert "Existing" in body            # token listed
    assert "/mcp" in body                # agent snippet
    assert "/settings/org" in body       # member-management link to org page


@pytest.mark.django_db
def test_old_settings_redirects_to_workspace(client_local, workspace):
    resp = client_local.get("/settings/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/settings/workspace"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_workspace.py -q`
Expected: FAIL — 404 (`/settings/workspace` 없음).

- [ ] **Step 3: 뷰 구현**

`tuckit/web/views/settings.py`에서 `settings` 함수를 리다이렉트로 바꾸고 `workspace_settings`를 추가한다. 파일 상단 import에 `redirect`, `is_org_admin`를 반영(이미 있으면 중복 금지):

```python
from django.shortcuts import redirect, render  # add redirect
from tuckit.core.services.orgs import is_org_admin  # add

def settings(request):
    return redirect("web:settings_workspace")


def workspace_settings(request):
    ws = get_current_workspace(request)
    return render(request, "web/settings_workspace.html", {
        "workspace": ws,
        "org": ws.org if ws else None,
        "tokens": list(list_tokens(ws)) if ws else [],
        "mcp_url": request.build_absolute_uri("/mcp"),
        "can_admin": bool(ws and is_org_admin(request.user, ws.org)),
    })
```

- [ ] **Step 4: 라우트 추가**

`tuckit/web/urls.py`의 settings 블록에 추가(기존 `settings/` 라인은 그대로 두면 리다이렉트로 동작):

```python
    path("settings/workspace", settings_views.workspace_settings, name="settings_workspace"),
```

- [ ] **Step 5: 워크스페이스 템플릿 생성**

`tuckit/web/templates/web/settings_workspace.html` (옛 settings.html에서 초대 섹션을 제외하고 이관 + 스코프내비 + 멤버 링크 + (Task 3에서 채울) 위험구역 자리는 두지 않음 — 위험구역은 Task 3에서 추가):

```django
{% extends "web/base.html" %}
{% block main %}
  {% include "web/partials/_settings_scopenav.html" with active='workspace' %}
  <div class="topbar"><h1 class="area-title">워크스페이스 설정</h1></div>

  <section class="group">
    <div class="group-label">워크스페이스 이름</div>
    <div class="settings-name" x-data="{editing: false, name: '{{ workspace.name|escapejs }}'}">
      <span class="settings-name-display" x-show="!editing" x-on:click="editing = true" x-text="name"></span>
      <input name="name" class="title-edit" x-show="editing" x-cloak x-model="name"
             hx-post="{% url 'web:workspace_rename' %}" hx-trigger="blur, keydown[key=='Enter']"
             hx-vals="js:{name: name}" hx-swap="none"
             x-on:keydown.enter="editing = false" x-on:blur="editing = false">
    </div>
  </section>

  <section class="group">
    <div class="group-label">API 토큰</div>
    <div class="empty muted">에이전트가 MCP로 이 워크스페이스에 연결할 때 사용하는 토큰입니다.</div>
    <div id="tokens-list" class="panel">
      {% for token in tokens %}
        {% include "web/partials/_token_row.html" %}
      {% empty %}
        <div class="empty muted">아직 토큰이 없습니다</div>
      {% endfor %}
    </div>
    <form class="token-add" hx-post="{% url 'web:token_create' %}" hx-target="#tokens-list" hx-swap="afterbegin"
          hx-on::after-request="this.reset()">
      <input name="name" placeholder="＋ 토큰 이름 (예: Claude Code)">
    </form>
  </section>

  <section class="group">
    <div class="group-label">멤버</div>
    <div class="empty muted">멤버와 초대는 조직 단위로 관리됩니다. <a href="{% url 'web:settings_org' %}">조직 설정에서 관리 →</a></div>
  </section>

  <section class="group">
    <div class="group-label">에이전트 연결</div>
    <div class="empty muted">아래 명령으로 Claude Code에 이 워크스페이스를 MCP 서버로 등록하세요.</div>
    <pre class="mcp-snippet"><code>claude mcp add --transport http tuck-it {{ mcp_url }} --header "Authorization: Bearer &lt;token&gt;"</code></pre>
  </section>
{% endblock %}
```

- [ ] **Step 6: 옛 템플릿 삭제**

```bash
git rm tuckit/web/templates/web/settings.html
```

- [ ] **Step 7: 스코프 내비 재지정**

`tuckit/web/templates/web/partials/_settings_scopenav.html`의 워크스페이스 링크를 `settings_workspace`로:

```django
<div class="scopenav">
  <a class="scope {% if active == 'org' %}on{% endif %}" href="{% url 'web:settings_org' %}">조직{% if org %} · {{ org.name }}{% endif %}</a>
  <a class="scope {% if active == 'workspace' %}on{% endif %}" href="{% url 'web:settings_workspace' %}">워크스페이스{% if workspace %} · {{ workspace.name }}{% endif %}</a>
</div>
```

- [ ] **Step 8: 사이드바 재지정**

`tuckit/web/templates/web/partials/_sidebar.html`의 ⚙ 설정 링크(현재 19-20행)를 교체:

```django
  <a class="nav muted{% if request.resolver_match.url_name == 'settings_workspace' or request.resolver_match.url_name == 'settings_org' %} nav--active{% endif %}"
     href="{% url 'web:settings_workspace' %}">{% icon "settings" %}<span class="nav-label">설정</span></a>
```

- [ ] **Step 9: 기존 테스트를 새 경로로 갱신**

`tests/web/test_settings.py`에서 `/settings/`를 GET하는 두 테스트를 `/settings/workspace`로 바꾼다(POST 엔드포인트 테스트는 그대로):

- `test_settings_page_lists_masked_tokens`: `resp = client_local.get("/settings/")` → `resp = client_local.get("/settings/workspace")`
- `test_token_list_is_a_panel`: `client_local.get("/settings/")` → `client_local.get("/settings/workspace")`

- [ ] **Step 10: 통과 확인**

Run: `uv run pytest tests/web/test_settings_workspace.py tests/web/test_settings.py -q`
Expected: PASS.

- [ ] **Step 11: 커밋**

```bash
git add tuckit/web/views/settings.py tuckit/web/urls.py tuckit/web/templates/web/settings_workspace.html tuckit/web/templates/web/partials/_settings_scopenav.html tuckit/web/templates/web/partials/_sidebar.html tests/web/test_settings_workspace.py tests/web/test_settings.py
git rm tuckit/web/templates/web/settings.html
git commit -m "feat(web): /settings/workspace page; /settings/ redirects; nav repointed"
```

---

### Task 3: 워크스페이스 삭제 (위험 구역)

**Files:**
- Modify: `tuckit/web/views/settings.py`
- Modify: `tuckit/web/urls.py`
- Modify: `tuckit/web/templates/web/settings_workspace.html`
- Test: `tests/web/test_settings_workspace.py`

**Interfaces:**
- Consumes: `delete_workspace` (Task 1), `is_org_admin`, `get_current_workspace`.
- Produces: URL name `web:workspace_delete` (`settings/workspace/delete`, POST). 성공 시 삭제한 ws가 현재 활성이면 세션 `active_workspace_id`를 비우고 `/`로 리다이렉트(302). 마지막 워크스페이스면 400.

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_workspace.py`에 추가:

```python
from tuckit.core.models import Org, OrgMember, User, Workspace
from tuckit.core.services.orgs import create_workspace


def _login(client, user, ws):
    client.force_login(user)
    session = client.session
    session["active_workspace_id"] = ws.id
    session.save()


@pytest.fixture
def admin_two_ws(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    admin = User.objects.create(username="a@a.com", email="a@a.com")
    OrgMember.objects.create(user=admin, org=org, role="admin")
    ws1 = create_workspace(org, "One")
    ws2 = create_workspace(org, "Two")
    return client, org, admin, ws1, ws2


@pytest.mark.django_db
def test_admin_deletes_workspace(admin_two_ws):
    client, org, admin, ws1, ws2 = admin_two_ws
    _login(client, admin, ws1)
    resp = client.post("/settings/workspace/delete")
    assert resp.status_code == 302
    assert not Workspace.objects.filter(id=ws1.id).exists()
    assert Workspace.objects.filter(id=ws2.id).exists()
    assert client.session.get("active_workspace_id") is None


@pytest.mark.django_db
def test_cannot_delete_last_workspace_via_view(admin_two_ws):
    client, org, admin, ws1, ws2 = admin_two_ws
    ws2.delete()  # leave org with a single workspace (ws1)
    _login(client, admin, ws1)
    resp = client.post("/settings/workspace/delete")
    assert resp.status_code == 400
    assert Workspace.objects.filter(id=ws1.id).exists()


@pytest.mark.django_db
def test_member_cannot_delete_workspace(admin_two_ws):
    client, org, admin, ws1, ws2 = admin_two_ws
    member = User.objects.create(username="m@a.com", email="m@a.com")
    OrgMember.objects.create(user=member, org=org, role="member")
    _login(client, member, ws1)
    resp = client.post("/settings/workspace/delete")
    assert resp.status_code == 403
    assert Workspace.objects.filter(id=ws1.id).exists()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_workspace.py -k delete -q`
Expected: FAIL — 404.

- [ ] **Step 3: 뷰 구현**

`tuckit/web/views/settings.py`에 추가(상단 import에 `require_POST`는 이미 있음; `delete_workspace`를 orgs import에 더한다):

```python
from tuckit.core.services.orgs import delete_workspace  # add to orgs import group


@require_POST
def workspace_delete(request):
    ws = get_current_workspace(request)
    if ws is None or not is_org_admin(request.user, ws.org):
        return HttpResponseForbidden("권한이 없습니다")
    try:
        delete_workspace(ws)
    except InvalidValue as exc:
        return HttpResponse(str(exc), status=400)
    if request.session.get("active_workspace_id") == ws.id:
        request.session.pop("active_workspace_id", None)
    return redirect("web:home")
```

- [ ] **Step 4: 라우트 추가**

`tuckit/web/urls.py`에 추가:

```python
    path("settings/workspace/delete", settings_views.workspace_delete, name="workspace_delete"),
```

- [ ] **Step 5: 위험 구역 UI 추가**

`settings_workspace.html`의 마지막 `{% endblock %}` 바로 앞에 추가:

```django
  {% if can_admin %}
  <section class="group">
    <div class="group-label danger">위험 구역</div>
    <form hx-post="{% url 'web:workspace_delete' %}" hx-confirm="이 워크스페이스와 모든 Area·항목이 삭제됩니다. 계속할까요?">
      <button type="submit" class="btn danger">워크스페이스 삭제</button>
    </form>
  </section>
  {% endif %}
```

- [ ] **Step 6: 통과 확인**

Run: `uv run pytest tests/web/test_settings_workspace.py -q`
Expected: PASS.

- [ ] **Step 7: 커밋**

```bash
git add tuckit/web/views/settings.py tuckit/web/urls.py tuckit/web/templates/web/settings_workspace.html tests/web/test_settings_workspace.py
git commit -m "feat(web): delete workspace from danger zone (admin+, last-workspace guard)"
```

---

### Task 4: 멤버 초대 UI를 조직 페이지로 이관

**Files:**
- Modify: `tuckit/web/views/settings_org.py`
- Modify: `tuckit/web/templates/web/settings_org.html`
- Test: `tests/web/test_settings_org.py`

**Interfaces:**
- Consumes: `Invitation` 모델, 기존 뷰 `web:invite_create` / `web:invite_cancel`(변경 없음), 파셜 `_invite_row.html`.
- Produces: `org_settings` 컨텍스트에 `invitations` 추가; 조직 페이지에 초대 목록 + 생성 폼.

- [ ] **Step 1: 실패 테스트 작성**

`tests/web/test_settings_org.py`에 추가(파일 상단에 `Invitation` import를 반영):

```python
from tuckit.core.models import Invitation  # add to existing model imports


@pytest.mark.django_db
def test_org_page_shows_invite_form_and_pending(org_ctx):
    client, org, owner, member, ws = org_ctx
    Invitation.objects.create(org=org, email="pending@x.com", role="member", token="tok-abc")
    _login(client, owner, ws)
    body = client.get("/settings/org").content.decode()
    assert "web:invite_create" not in body            # url resolved, not literal
    assert 'hx-post="/settings/invites"' in body       # invite form present on org page
    assert "pending@x.com" in body                     # pending invite listed
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/web/test_settings_org.py -k invite -q`
Expected: FAIL — 초대 폼/목록이 조직 페이지에 없음.

- [ ] **Step 3: 뷰 컨텍스트에 invitations 추가**

`tuckit/web/views/settings_org.py`의 `org_settings`를 수정 — 상단 import에 `Invitation`을 더하고 컨텍스트에 `invitations`를 추가:

```python
from tuckit.core.models import Invitation, OrgMember  # add Invitation

# inside org_settings(...), extend the render context dict with:
        "invitations": list(Invitation.objects.filter(org=org, accepted_at__isnull=True)) if org else [],
```

- [ ] **Step 4: 조직 페이지에 초대 섹션 추가**

`settings_org.html`의 "멤버 · 역할" 섹션 바로 다음에 초대 섹션을 추가(admin+만 폼 노출):

```django
  {% if can_admin %}
  <section class="group">
    <div class="group-label">멤버 초대</div>
    <div class="empty muted">이메일과 역할을 지정해 조직에 멤버를 초대하세요.</div>
    <div id="invite-list" class="panel">
      {% for inv in invitations %}
        {% include "web/partials/_invite_row.html" with inv=inv %}
      {% empty %}
        <div class="empty muted">대기 중인 초대가 없습니다</div>
      {% endfor %}
    </div>
    <form class="token-add" hx-post="{% url 'web:invite_create' %}" hx-target="#invite-list" hx-swap="afterbegin"
          hx-on::after-request="this.reset()">
      <input type="email" name="email" placeholder="이메일" required>
      <select name="role">
        <option value="member">멤버</option>
        <option value="admin">관리자</option>
      </select>
      <button type="submit">초대</button>
    </form>
  </section>
  {% endif %}
```

- [ ] **Step 5: 통과 확인 + 전체 회귀**

Run: `uv run pytest tests/web/test_settings_org.py -k invite -q`
Expected: PASS.

Run: `uv run pytest -q`
Expected: PASS (기존 `tests/web/test_settings_invites.py` 포함 무회귀 — 초대 엔드포인트는 변경되지 않음).

- [ ] **Step 6: 커밋**

```bash
git add tuckit/web/views/settings_org.py tuckit/web/templates/web/settings_org.html tests/web/test_settings_org.py
git commit -m "feat(web): move member-invite UI to the org settings page"
```

---

## Self-Review (작성자 체크)

- **스펙 커버리지(2단계):** 워크스페이스 페이지(이름·토큰·에이전트) = Task 2 · 멤버 안내 링크 = Task 2 · 워크스페이스 삭제(admin+, 마지막 ws 보호, 캐스케이드) = Task 1·3 · `/settings/` 하위호환 리다이렉트 = Task 2 · 초대 UI 조직 이관 = Task 4. ✓
- **2단계 밖(후속):** Area 인라인 CRUD(3단계), 계정 페이지·조직 전환기·`create_org`·`leave_org`(4단계), cloud 플랜 슬롯(5단계).
- **플레이스홀더 스캔:** 모든 스텝에 실제 코드·명령·기대출력 포함. 없음. ✓
- **타입 일관성:** `delete_workspace(workspace)`(Task 1)이 Task 3 뷰 호출부와 일치. `workspace_settings` 컨텍스트가 제공하는 `can_admin`을 Task 3 위험구역 템플릿이 사용. scopenav/sidebar가 참조하는 `web:settings_workspace`는 Task 2에서 등록. `web:settings`는 리다이렉트로 유지되어 잔여 참조가 깨지지 않음. ✓
- **회귀 주의:** `test_settings.py`의 두 GET을 `/settings/workspace`로 갱신(Task 2 Step 9). `test_settings_invites.py`는 엔드포인트 불변이라 그대로 통과. 옛 `settings.html` 삭제는 더 이상 렌더되지 않으므로 안전.
- **경계:** 새 코드 전부 공개 코어. billing 문구 없음. 워크스페이스 페이지에 멤버/초대/플랜 없음(링크만) — 멤버·초대는 조직 레벨 유지.
