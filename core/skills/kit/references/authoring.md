# 저작 — kit에 무언가 추가할 때

## 🔑 먼저 — **스킬을 만들 일이 아닐 수 있다**

새 스킬은 마지막 선택지다. 순서대로 배제한다:

| 담을 것 | 어디 | 왜 |
|---|---|---|
| **매번 참인 짧은 규칙** | `{{AGENT_FILE}}` | 스킬로 만들면 소환돼야만 먹는다 |
| **모든 작업에 공통인 생명주기** | 🔑 `backbone/` (단계) 또는 `backbone/profiles/` | 전역 진행 순서를 도메인 스킬마다 복제하지 않는다 |
| **특정 user job의 반복 절차** | 기존 스킬 또는 ✅ 새 스킬 | 입력·판단·완료조건이 그 작업에만 속한다 |
| **좋은 결과의 기준** | `doctrine/global.md` 또는 profile의 독트린 | 정책(하면 안 되는 것)과 다르다 |
| **어디서만 참인 규칙** | `scopes/` | 회사·오픈소스·개인 |
| **기존 스킬과 트리거가 겹침** | 그 스킬의 `references/` | 아래 P1 |
| **도메인 지식 · 새 트리거** | ✅ 새 스킬 | |

## 인라인 디렉티브 vs 슬래시 커맨드 — 세션 손잡이를 어디에

세션 동작을 바꾸는 **손잡이**(레지스터·모드 등)를 새로 만들 때, 둘 중 뭘 고를지.

| 축 | **인라인 디렉티브** `==x==` | **슬래시** `/x` |
|---|---|---|
| 위치 | 프롬프트 **아무 데나** — 요청과 한 줄에 섞임 (`"이거 고쳐줘 ==chat=="`) | 프롬프트 **맨 앞만** |
| 지속 변형 | ✅ `==x on/off==` 로 세션 유지 (continuity key로 세션 전환을 넘어 삶) | 매번 다시 |
| 발견성 | ❌ 자동완성 없음 — 알아야 씀 | ✅ 메뉴에 뜸 |
| 파싱 | 산문 grep → **오탐 위험**(구조로 막음, 아래) | argv → 견고 |
| 구현 자리 | `hooks/inject-state.sh` | `commands/<x>.md` |

**판정**: *normal 요청에 얹는 수정자·자세*(간결도·논의-우선·즉답)면 → **인라인**. *독립적으로 실행되는 동작*(레지스터를 **명시적으로** 지정, 워크플로 트리거)이면 → **슬래시**. 둘 다여도 된다 — `register` 는 `/register`(명시)와 `==tldr==`(인라인) 둘 다 있다.

**인라인 디렉티브 구현 규약** (기존 `tldr`·`chat`·`asap` 과 맞춘다):

- 감싸개 `==` `--` 둘 다 인식. 토큰은 영단어(+한국어 별칭 선택).
- **오탐방어 필수**: ① 코드펜스·인라인 코드 제거 ② **첫 비어있지 않은 줄**의 지시일 때만 → 붙여넣은 코드 속 `--x--` 는 안 터진다.
- 지속은 `$(tr_state)/<x>/<tmux명>` 플래그. register 와 직교하면 **별도 플래그**(같은 축이면 register 값으로).
- **매 턴 상기**: 켜져 있으면 inject-state 가 매 턴 그 모드를 재주입(배경화 방지).
- 용어는 **"인라인 디렉티브"**(kit 공식) — "명령/토큰"이라 부르지 않는다.

## 표기 규약 — 기호마다 자리가 있다

kit 전체에서 쓰는 기호다. **아무 데나 붙이면 아무 데도 안 붙인 것과 같아진다.**

| 기호 | 뜻 | 언제 |
|---|---|---|
| 🔑 | **핵심 — 놓치면 틀린다** | 그 블록에서 **빠지면 결론이 뒤집히는** 지점. 단순 강조가 아니다 |
| ⚠️ | 주의 | 조심하면 되는 것 |
| ⛔ | **금지** | 하면 안 되는 것 (정책) |
| ❌ | 안 됨 · 기각 | 대안 표에서 버린 것 |
| 🔻 | 폐기됨 | 있었다가 없앤 것 |
| ✅ | 완료 · 채택 | |
| ⭐ | 추천 | 후보 중 미는 것 |
| ⬜ | 미정 · 비어 있음 | 자리는 있는데 안 채운 것 |
| 👤 / 🤖 | 사람이 읽나 / AI가 읽나 | `_local-docs` 구조 축 |

> **왜 🔑인가 (2026-08-06)**: 원래 🔴이었는데 ⚠️·⛔·❌·🔻가 이미 붉은 계열이라 **뜻이 정반대인 "핵심"이 경고 무리로 읽혔다.** 가장 많이 쓰는 기호가 잘못된 신호를 주고 있었다. 🔑은 **"이게 열쇠다"**로 바로 읽히고 경고 팔레트 밖이다.

## 원칙 (P1~P5)

| | |
|---|---|
| **P1** | **스킬 = 소환 단위.** *"이럴 때 이걸 읽는다"*의 그 단위다. **트리거가 같으면 한 스킬** — 도메인이 같다는 이유로 묶지 않는다 |
| **P2** | 🔑 **크기는 쪼개서가 아니라 `references/`로 조절한다.** `SKILL.md` = 트리거 + 분기 지도. 깊이는 references에 |
| **P3** | **이름 = user job을 찾는 손잡이.** 짧은 kebab-case로 짓고, 동작이 핵심이면 action-oriented 이름을 허용한다 |
| **P4** | 🔑 **전역 lifecycle은 backbone, domain-specific procedure는 skill.** 같은 단계를 양쪽에 복제하지 않는다 |
| **P5** | **한 user job = 한 owner.** 주제보다 trigger·입력·결과·절차가 같은지를 보고 합치거나 나눈다 |

## 발동 계약과 두 load

`description`은 skill 내용이 로드되기 전에 모델이 보는 **context pointer**다. 기능을 한 구절로
말하고 실제로 다른 요청 branch만 trigger로 적는다. 같은 branch의 동의어를 나열하거나 본문
정체성을 반복하지 않는다.

| 비용 | 의미 | 선택 |
|---|---|---|
| context load | description·전역 문서처럼 매 요청에 노출되는 비용 | 자동 발견 가치가 있을 때만 지불 |
| cognitive load | 사용자가 skill 이름과 호출 시점을 기억하는 비용 | 명시 호출 전용일 때 지불 |

- 모델이 스스로 찾아야 하거나 다른 workflow가 호출해야 하면 자동 발견 가능 상태를 유지한다.
- 사람이 이름을 직접 입력할 때만 필요한 skill은 명시 호출 전용을 고려한다.
- 이 선택의 표현 방식은 host별 manifest·invocation 계약이 소유한다. 공통 source에 한 host의
  field를 보편 규칙처럼 넣지 않는다.
- 발동이 불안정하면 본문을 상시 로드하기 전에 description의 기능·branch·가까운 비대상 경계를
  먼저 고친다.

## 저작 흐름

1. 변경을 create·port·refactor·merge·split으로 분류하고 user job, 입력, 관찰 가능한 결과,
   권한 경계와 비목표를 적는다. 하나의 operation으로 닫히지 않으면 새 skill을 만들지 않는다.
2. 기존 skill을 trigger·결과·방법으로 검색한다. 같은 job의 owner가 있으면 새 디렉터리보다 그
   owner를 보강한다.
3. repository 규약, 강한 이웃 skill 하나, 대상의 inbound·outbound route와 recipe registration을
   읽는다. 이웃의 domain 문구를 형식처럼 복사하지 않는다.
4. 외부 skill을 port하면 pinned revision과 license를 먼저 읽는다. portable method와 제품명,
   host syntax, 낡은 경로를 분리하고 canonical NOTICE에 필요한 attribution을 남긴다.
5. 본문보다 routing contract를 먼저 쓴다. name·description, 입력, 결과, authority, non-goal,
   completion condition이 같은 job을 가리켜야 한다.
6. domain procedure는 입력 검증부터 완료조건까지 시간순으로 쓴다. 모델이 추측할 갈림선과
   안전상 필요한 금지는 명시하되, 기본 능력을 되풀이하는 의례 문장은 제거한다.
7. 모든 branch가 필요한 절차와 치명적 제약은 `SKILL.md`에 둔다. branch 전용 schema·catalog·
   예시는 load 조건이 선명할 때만 `references/`로 내린다.
8. split은 독립 trigger가 실제로 필요하거나 branch별 load를 줄이거나, 관찰된 조기 종료를
   실제 context 경계로 차단할 때만 한다. 줄 수만으로 나누지 않는다.
9. 반복 parsing·validation처럼 결정성이 필요한 일만 `scripts/`로 만들고, 출력 형태 자체가
   계약일 때만 `assets/`를 둔다. 빈 디렉터리는 만들지 않는다.
10. rename·merge·split이면 live route, recipe, manifest, catalog와 obsolete alias를 같은 변경에서
    이관한다.
11. source와 양 target 생성물을 검증한 뒤 실제 발동 probe를 수행한다. 최소 positive 2개와
    nearest-negative 2개를 쓰고, host에서 model routing을 실행하지 못했다면 정적 검증과 구분해
    **미검증**으로 보고한다.

각 중요한 단계의 완료조건은 관찰 가능하고 그 단계가 맡은 범위를 충분히 요구해야 한다.
다만 모든 문장 뒤에 같은 완료 문구를 붙이지 말고, 조기 종료 가능성이 있는 경계에만 둔다.

## 스캐폴딩

`skills/<name>/SKILL.md`:

```markdown
---
name: <폴더명과 동일. 소문자-하이픈>
description: <기능 + 실제 trigger branch + 가까운 비대상 경계>
---
```

- **`description`은 항상 로드되는 발동 pointer다** — 본문은 소환된 뒤에야 읽힌다. 기능을 앞에 두고 실제 요청 branch를 짧게 적는다.
- 본문 첫 블록은 **갈림선**을 세운다 — *"먼저, X냐 Y냐"*. 읽는 쪽이 어디로 갈지 한 문장으로 알게.
- 긴 것은 `references/<주제>.md`로.

## 체크리스트

- [ ] 위 배제 표를 통과했나? (진짜 새 스킬이 맞나)
- [ ] 기존 owner와 trigger·결과·방법이 겹치지 않나? 겹치면 보강·merge
- [ ] `description`이 기능·실제 branch·가까운 비대상 경계를 구분하나
- [ ] name·입력·결과·authority·완료조건이 하나의 user job으로 닫히나
- [ ] 공통 경로와 branch 전용 reference의 load 조건이 선명한가
- [ ] 이름이 user job을 드러내는 짧은 kebab-case인가
- [ ] 중요한 단계의 완료조건이 관찰 가능하고 충분한가
- [ ] positive 2개·nearest-negative 2개 routing probe 결과가 있는가
- [ ] 특정 repo가 대상이면 **`## 대상 repo`**를 적었나 (경로 · 참조해결: 로컬 → clone → 신설)
- [ ] 외부(odin 등) 참조는 **소프트의존 + fallback**인가 — *"있으면 우선, 없으면 …"*
- [ ] 외부 플러그인을 새로 들였으면 **`INTEGRATIONS.md`에 등록**했나
- [ ] port라면 pinned source·license·canonical attribution을 기록했나
- [ ] rename·merge·split의 live route와 registration을 함께 이관했나
- [ ] **최소로 시작**했나 (훅·서브에이전트 과설계 아님)

## 검증

`tools/validate` — 하드 규칙(`name`==폴더명 · `description` 존재 · 참조 파일 존재 · secret 없음)을 강제한다.
양 target build·생성물 validator와 routing probe 결과까지 분리해서 보고한다. 정적 validator는
metadata와 구조를 증명할 뿐 실제 model 발동을 증명하지 않는다. **모든 적용 가능한 gate 통과 후 커밋.**

🔑 커밋했다고 설치본에 반영되는 게 아니다. target별 version·cache·재설치 규칙은 `SKILL.md`의 delivery capability를 따른다.

---

## 규약 — 스킬을 쓸 때 지키는 것

*(구 `CONVENTIONS.md`에서. 나머지 절은 새 구조가 대체했다 — scope 배치는 플러그인이 하나라 사라졌고, tier·메뉴판·사이징은 위 P1~P5가 흡수했다)*

### 외부·타 스킬 위임 — **표준 문구로**

매번 제각각 쓰지 말고 이 형태로:

> `<plugin>:<skill>` 있으면 그 워크플로 **우선 활용**, 없으면 **`<자체 fallback>`**. 하드의존·자동설치 아님.

- fallback은 반드시 **구체적으로** — 무엇으로 대체하는지.
- 🔑 **예시로 쓰는 외부 스킬명이 실재하는지 확인한다.** (2026-08-05: 규약의 예시가 `odin:code-review`였는데 odin엔 그 스킬이 없었다 — 규약을 그대로 베껴 **없는 스킬을 3곳에서 참조**하고 있었다)
- 외부를 새로 들이면 **`INTEGRATIONS.md`에 등록**한다(모드·상태). 인라인 문구는 그대로 두고 — 중앙 목록은 조회용이라 **상보적**이다.

### 특정 repo를 대상으로 하는 스킬

cwd가 아니라 **설정으로 연결된 git repo**를 보는 스킬.

1. **본문에 `## 대상 repo` 섹션** — 이름·원격·구조·경로. skill→repo 매핑의 조회 지점이다.
2. **source에는 실제 경로를 박지 않는다** — runtime profile 같은 설정 계약을 사용한다. kit·인프라·유틸 repo는 bare, 일반 작업 프로젝트는 중첩 layout을 기본 후보로 둘 수 있다.
3. **참조 해결은 단계적으로** — 없다고 죽지 않게:
   ```
   로컬에 있나 → 사용 (필요 시 pull)
   원격에 있나 → clone (확인 후)
   없으면      → 신설 (확인 후)
   ```
4. **그 repo의 규약을 따른다** — 구조·secret·로그 형식은 repo가 정본이다. 스킬에 복제하지 않는다.

### 이력

**별도 이력 스킬은 없다 — git이 정본이다.**

- 🔑 **git이 아는 걸 파일에 중복해 쓰지 않는다.**
- 큐레이션 롤업(`git log`가 시끄러울 때)만 **목록 + commit 링크**로: kit `HISTORY.md` · 프로젝트 기록 · 홈랩 `log`.
- append-only · 절대일자 · **최신이 위**(실행 로그류는 시간순도 허용 — 파일 안에서 일관되면 된다).
