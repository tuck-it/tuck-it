# 관리 표면(Org / Workspace / Area) 설계

- **날짜:** 2026-07-12
- **레포:** `tuckit` (공개, BSL 1.1) — 신규 코드 전부 코어. cloud는 중립 슬롯 하나만 채움.
- **상태:** 설계 확정, 구현 계획 대기
- **비고:** 이 문서는 `docs/superpowers/`(gitignore됨) 아래에 있으며 **커밋하지 않는다**.

## 1. 문제 / 동기

제품 UI(캡처 → 상태 점 → 보드 = "밀어넣으면 보이는 로드맵")는 완성도가 있으나, 그 **컨테이너를 통제하는 화면**이 없다. 뷰 함수·엔드포인트는 일부 있어도 실제 페이지·CRUD가 비어 있음:

- **Org:** 조직 이름 변경 ✗, 멤버·역할 목록 보기 ✗(대기 초대만), 역할 변경/멤버 제거 ✗, 나가기/삭제 ✗. 초대 생성/취소만 `settings`에 묻혀 있음.
- **Workspace:** `workspace_create`는 POST 전용(생성 UI가 어느 화면에도 없음), 전환은 민짜 `<select>`, 이름변경은 `settings`에 현재 것만. 목록/삭제/워크스페이스별 허브 ✗.
- **Area:** 생성 + 보기(C·R)만. 이름변경·삭제·순서변경(U·D) ✗.
- `settings.html`은 "현재 워크스페이스" 한정 잡탕(이름+토큰+초대+MCP)이라 org 단위와 workspace 단위가 뒤섞임.

**컨셉:** "내 프로젝트에서 일어나는 모든 것을 통제하고 있다는 편안함". Confluence/Jira식 "복잡하고 알 수 없는 계층"의 반대. 계층을 **숨기지 않되**(사용자 결정) 시각적 차분함(Warm Greige)과 명료한 담김 구조로 편안함을 만든다.

## 2. 목표 / 비목표

**목표**
- Org / Workspace / Area의 완전한 관리 표면(CRUD + 멤버/역할)을 코어에 추가.
- 기존 Warm Greige 디자인 시스템(`tokens.css`, `base.html`, HTMX + Alpine)과 완전한 시각적 일관성.
- 멀티조직(사용자 ⊇ 여러 조직)을 자연스럽게 다루는 진입점.
- 셀프호스트에서도 그대로 동작(중립). cloud는 플랜/결제 슬롯만 주입.

**비목표(이번 범위 밖)**
- URL을 세션 기반 → 슬러그 기반(`/o/<org>/w/<ws>/…`)으로 바꾸는 앱 전역 리팩터. (미래: 딥링크 필요 시 승격)
- 전용 "조직 허브" 랜딩 페이지(`/orgs`).
- 소셜 로그인/이메일 인증/온보딩 위저드.
- cloud의 결제 흐름 자체(Paddle) — 별도 작업.

## 3. 정보 구조(IA) 결정

- **하이브리드:** Area는 **사이드바 인라인**에서 관리(자기가 사는 곳). Org/Workspace/멤버/토큰은 **설정 허브**(별도 라우트 페이지).
- **URL 깊이 = A안(스코프 라우트, 세션 기반):** 경로 뿌리가 스코프를 이름으로 밝힌다. 앱의 기존 세션 기반 "현재 워크스페이스"와 마찰 없음.
  - `/settings/account` — 개인 계정 + 내 조직 목록
  - `/settings/org` — 현재 조직(현재 워크스페이스의 org)
  - `/settings/workspace` — 현재 워크스페이스
  - 기존 `/settings/` → `/settings/workspace`로 리다이렉트(하위호환).
- **담김 구조:** `/settings/org`가 자기 워크스페이스 목록을 품고, 항목에서 `/settings/workspace`로 드릴다운. 조직/워크스페이스가 **형제가 아니라 부모-자식**으로 보이게 한다.
- **멤버·결제는 조직 레벨에만.** 워크스페이스 페이지엔 멤버/결제 없음("멤버는 조직 설정에서" 링크만).
- **전환·생성은 앱 크롬(사이드바)에.** 설정은 구성 전용.
- 설정 상단에 스코프 탭(계정 / 조직·<name> / 워크스페이스·<name>)으로 세 라우트 이동.

### 근거(업계 리서치 요약)
Linear(계정/워크스페이스/팀)·Notion(계정/워크스페이스/팀스페이스)·Slack(그리드org/워크스페이스/채널)가 우리 3단 중첩과 일치. 공통 패턴: (1) 스코프를 경로에 드러냄, (2) 멤버·결제는 상위(org)에만, Slack/Figma는 하위 admin의 결제 접근을 차단, (3) 전환·생성은 크롬의 스위처, (4) 3단 계층엔 모달보다 라우트 페이지, (5) 형제 함정 회피 = URL·스위처 모두에서 ws를 org 밑에 중첩.

## 4. 화면 사양

공통 셸: 기존 `base.html`(사이드바 + main). 설정 페이지는 `base.html`을 확장하고 main에 스코프 탭 + 카드 섹션.

### 4.1 사이드바 크롬 (모든 화면 공통, 개편)
- **조직 전환기**(상단): `현재조직 ▾`. 펼치면 사용자의 각 조직 헤더(역할 배지) 아래에 그 조직의 워크스페이스가 **들여쓰기**되어 나열 + `＋ 워크스페이스`. 맨 아래 `＋ 새 조직 만들기`. 조직/ws가 같은 평면에 안 놓임.
  - 워크스페이스 클릭 → 세션 `active_workspace_id` 갱신 후 `/`.
  - 다른 조직의 ws 클릭 → 그 조직으로 전환(= 그 ws로 전환).
- **워크스페이스 목록**(현재 조직): 현재 표시 + 다른 것 전환 + `＋ 새 워크스페이스`(admin+).
- **영역(Area) 인라인**(현재 ws): 각 Area에 hover 시 `✎`(이름변경, 인라인 편집 — settings의 rename 패턴 재사용) / `✕`(삭제, 확인 모달) 노출. **드래그로 순서변경**(sortable.js + `rank`/`rank_for`, slice/bite 패턴 재사용). `＋ 새 영역`(기존).
- 하단: `⚙ 설정`, `로그아웃`.

### 4.2 `/settings/account` — 계정(= 조직 리스트)
- **프로필:** 이메일(표시), 표시 이름(편집), 비밀번호(Django 기본 `PasswordChangeView` 연결), 테마(기존 localStorage 토글).
- **내 조직들:** 각 조직 = 아이콘 + 이름 + 워크스페이스 수 + 내 역할 배지 + `열기`(전환) + `나가기`(멤버/관리자만; 단독 소유자는 불가). `＋ 새 조직 만들기`(→ `create_org`).
- **대기 중인 초대:** 이메일로 온 초대 목록 + `수락`/`거절`. (`get_pending_invitation`/`accept_invitation` 재사용; 이메일 매칭 조회 추가.)

### 4.3 `/settings/org` — 조직
- **조직 이름:** 인라인 편집(`rename_org`, admin+).
- **플랜·결제 슬롯(cloud):** 코어는 비어 있는 include 슬롯. cloud가 플랜/좌석/업그레이드 CTA 주입. (§6)
- **멤버·역할:** 멤버 목록(아바타/이메일/역할). 역할 변경 드롭다운(`change_member_role`), 제거(`remove_member`), 대기 초대 표시 + 취소(기존), 이메일 초대(기존 `create_invitation`, 좌석 한도 훅 그대로 적용).
- **이 조직의 워크스페이스:** 목록 + 각 `설정 →`(→ 그 ws로 전환 후 `/settings/workspace`) + `＋ 새 워크스페이스`.
- **위험 구역:** `조직 삭제`(owner만, 확인 모달, 캐스케이드). 마지막 조직은 삭제 불가(사용자는 최소 1개 조직 유지).

### 4.4 `/settings/workspace` — 워크스페이스
- **이름:** 인라인 편집(기존 `workspace_rename`).
- **API 토큰:** 기존 그대로 이관.
- **에이전트 연결(MCP):** 기존 그대로 이관.
- **멤버 안내:** "멤버는 조직 설정에서 관리됩니다" + `/settings/org` 링크(멤버 UI 중복 금지).
- **위험 구역:** `워크스페이스 삭제`(admin+, 확인 모달, area/slice/bite 캐스케이드). 조직의 마지막 워크스페이스는 삭제 불가.

## 5. 백엔드 — 신규 서비스 (전부 `tuckit/core/services/`)

기존 재사용: `is_org_admin`, `seat_count`, `accessible_workspaces`, `user_can_access_workspace`, `create_workspace`, `create_area`/`list_areas`, 초대 CRUD, 토큰 CRUD, `rank_for`(순서변경 인프라).

신규(시그니처 초안):

**orgs.py / (신규) members.py**
- `rename_org(org, name)` — admin+.
- `list_user_orgs(user) -> list[{org, role, workspace_count}]` — 계정 페이지 + 스위처.
- `list_org_members(org) -> QuerySet[OrgMember]`.
- `change_member_role(org, member, role, *, by)` — owner만 owner/admin/member 변경. owner 강등/최후 owner 보호.
- `remove_member(org, member, *, by)` — admin+; owner 제거 불가(owner는 먼저 강등/이양).
- `leave_org(user, org)` — 단독 소유자면 거부(먼저 이양/삭제).
- `create_org(user, name) -> tuple[Org, Workspace]` — Org + owner OrgMember + 첫 Workspace(+inbox/Default) 생성. `register`의 org 부분 추출·재사용. `run_signup_hook` 호출 여부는 정책 결정(신규 조직도 cloud 구독 생성 필요 → 호출).
- `delete_org(org, *, by)` — owner만. 캐스케이드. 사용자의 마지막 조직이면 거부.

**workspaces**
- `delete_workspace(workspace, *, by)` — admin+. area/slice/bite 캐스케이드. org의 마지막 ws면 거부.

**areas.py**
- `rename_area(area, name)`.
- `delete_area(area)` — 캐스케이드(안의 slice·bite 함께 삭제). 확인은 UI에서. Inbox는 삭제 불가.
- `reorder_area(area, *, before=None, after=None)` — `rank_for` 사용.

각 서비스는 서비스 레이어에서 권한·불변식(최후 owner/최후 org/최후 ws/Inbox 보호)을 강제하고, 위반 시 기존 `exceptions.py`의 예외(`InvalidValue` 등, 필요시 `PermissionDenied`/`LastResource` 추가)를 던진다. 뷰는 얇게.

## 6. 공개/비공개 경계 (cloud 슬롯)

- 코어 `/settings/org` 템플릿에 **중립 include 슬롯** 하나:
  ```django
  {% if org_settings_panel %}{% include org_settings_panel %}{% endif %}
  ```
  `org_settings_panel`은 컨텍스트 프로세서가 `settings.TUCKIT_ORG_SETTINGS_PANEL`(dotted 템플릿 경로, 코어 기본 `None`)에서 채운다. 기존 `TUCKIT_SIGNUP_HOOK`/`TUCKIT_ENTITLEMENTS_HOOK` 패턴과 동일한 결의 확장.
- 코어는 좌석 **한도가 있을 때만** 중립적으로 "N/한도"를 표시할 수 있으나(‐ `resolve_entitlements`), 셀프호스트(무제한)에선 아무것도 안 보임. **플랜 이름·가격·업그레이드·결제 문구는 코어에 절대 없음** — 전부 cloud 슬롯 템플릿.
- cloud(`tuckit_cloud`)는 `TUCKIT_ORG_SETTINGS_PANEL = "billing/org_panel.html"`을 설정하고 템플릿 오버라이드 디렉터리로 그 템플릿을 제공.
- 이 스펙 문서 자체도 커밋 금지(공개 레포 오염 방지). `docs/superpowers/`는 `.gitignore`에 추가됨.

## 7. 권한 매트릭스

| 동작 | owner | admin | member |
|---|---|---|---|
| 조직 이름 변경 | ✓ | ✓ | ✗ |
| 멤버 초대/취소 | ✓ | ✓ | ✗ |
| 역할 변경 | ✓ | ✗ | ✗ |
| 멤버 제거 | ✓ | ✓(owner 제외) | ✗ |
| 워크스페이스 생성/삭제 | ✓ | ✓ | ✗ |
| Area CRUD | ✓ | ✓ | ✓(자기 ws) |
| 조직 나가기 | ✓(단독 owner 아니면) | ✓ | ✓ |
| 조직 삭제 | ✓ | ✗ | ✗ |

(초안 — 구현 계획에서 `is_org_admin` = owner∪admin 정의 재확인, owner 전용 게이트 추가.)

## 8. 오류 처리
- 서비스 예외 → 뷰에서 4xx + 인라인 메시지(HTMX 부분 스왑). 좌석 한도는 기존 402 패턴 유지.
- 불변식 위반(최후 owner/org/ws, Inbox 삭제)은 버튼 비활성 + 서버측 재검증(이중 방어).
- 위험 작업(조직/워크스페이스/Area 삭제)은 확인 모달(기존 capture 모달 Alpine 패턴 재사용).

## 9. 테스트
- 서비스 레이어 단위 테스트(권한·불변식 중심): 최후 owner 강등/제거 거부, 최후 org/ws 삭제 거부, Inbox 삭제 거부, 캐스케이드 정확성, `create_org` 부산물(첫 ws·inbox·훅).
- 뷰 테스트: 각 라우트 권한 게이트, 스코프 탭 렌더, 멀티조직 전환.
- 기존 `tests/web/test_seat_limit.py` 등 회귀 유지.

## 10. 구현 단계
1. **조직 페이지** — 이름·멤버 목록·역할변경·제거·초대(기존)·위험구역(삭제). members 서비스.
2. **워크스페이스 페이지** — 기존 settings 이관 + 삭제 + 위험구역 + 멤버 안내 링크.
3. **Area 인라인** — 이름변경·삭제(캐스케이드 확인)·순서변경(사이드바).
4. **계정 페이지 + 조직 전환기** — `list_user_orgs`·`create_org`·`leave_org`·초대 수락·중첩 스위처.
5. **cloud 플랜 슬롯** — `TUCKIT_ORG_SETTINGS_PANEL` 시임 + cloud 측 패널 템플릿(별도 tuckit-cloud 작업).

## 11. 미해결 / 향후
- 딥링크가 필요해지면 URL을 슬러그 기반(B안)으로 승격.
- 소유권 이양(transfer ownership) 흐름 — v1은 "강등 후 다른 owner 지정"으로 우회, 전용 UI는 향후.
- 조직 허브 랜딩(`/orgs`) — 보류.
