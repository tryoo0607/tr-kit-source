# 구조와 책임

## 현재 구조의 상태 — 2026-11-23

이 문서는 scratch source의 책임·배치를 설명한다. 기존 운영 설치본의 구조·활성 상태와 동일하다고 가정하지 않는다. 검증 범위와 후속 순서는 [검증 현황](verification.md#현재-판정--2026-11-23)과 [이관 현황](migration-status.md#현재-후속-순서--2026-11-23)을 참조한다.

- 공통 자체 skill53개와 별도 private 자체 skill9개, 공통/private의 대응 계층 구조를 유지한다. 각 업무는 자기 산출물과 검증을 소유한다.
- source와 native의 조립·설치 인터페이스를 구현했고 이전 묶음의 양 제품 격리 설치·초기 주입·hook·MCP와 대표 모델 업무/수동 압축·재개를 각각 시험했다. 서로 다른 revision/조건의 시험이며 전 기능·자연 발동·운영 적합 검증은 아니다.
- 후속5번에서 현재 공통 source/native 후보를 새로 조립하고 private exact pin4개를 정렬했다. private 형식 전달 교정·백업 목차도 새 묶음에 반영해 양 제품 격리 설치/초기 주입·연결·제거를 검증했다. 현재 계약과 시험 버전의 관계·한계는 [후보 검증 기록](decisions/20261123-candidate-pin-native-validation.md)을 따른다.
- 아래 ‘단계별 구조 이력’은 각 구현 당시의 파일 수·미실행 범위를 보존한다. 그 안의 ‘현재’·‘미연결’ 표현을 오늘의 상태로 사용하지 않는다.

## Native 재사용 인터페이스

공통 scripts/package.py가 자체 envelope·installation.json 생성을 소유하고 assemble.py가 승인된 자체 renderer를 받는다. 공통 lifecycle은 명시 identity와 실제 native 설치 목록을 검증한다. 공통 구현은 개인 패키지 이름/기능에 의존하지 않는다. private는 별도 source/native exact pin을 확인한 후 이 구현을 호출한다. 배치·실제 흐름·제품별 차이는 [native 연결 기록](decisions/20261120-native-private-interface.md)에 있다.

## 세션 재시작 배치

기존 `runtime_refresh.py`는 inspect/plan/apply와 native guard·접수를 유지한다. 새 `session_restart.py`가 재부팅 뒤에도 읽을 수 있는 선택·예외·UUID와 진행 기록을 소유하고 기존 transport/status/eligibility를 호출한다. 설치 시점과 runtime 소비를 구분하며 공통 계층만 사용한다. [결정·검증 한계](decisions/20261123-session-restart.md)를 따른다.

실제 파일 배치:

```text
common/base/skills/
├─ session/
│  ├─ SKILL.md
│  ├─ references/
│  │  ├─ runtime-refresh.md
│  │  └─ session-restart.md
│  └─ scripts/
│     ├─ runtime_refresh.py
│     └─ session_restart.py
└─ orca-update/
   └─ SKILL.md
tests/
├─ test_session_runtime_refresh.py
├─ test_session_restart.py
└─ test_native_package.py
```

읽기·실행 흐름:

```text
재시작 목록/선택 복원 요청
  → 수행자가 session SKILL.md의 배치 분기와 session-restart.md를 읽음
  → 수행자가 session_restart.py prepare/list 호출
    → prepare: 예외/self 기록 → 안전 대상 새 status → UUID/cwd/권한 저장 (exit 없음)
    → list: 기존 호스트 로컬 배치 읽기 (runtime/대화/상태 생성 없음)
  → native CLI 업데이트가 승인된 경우 수행자가 기존 공식 관리자 호출 → 버전/소유 재개 canary 대조
  → 나중 명시 요청에서 수행자가 session_restart.py restart/restore/verify 호출
    → 실행: 현재 Orca inventory/guard → 선택 native identity 대조
      → restart: 검증된 Codex 정상 종료/exact resume; Claude 즉시 종료·shell 전이 자동 검증은 미지원으로 수동
      → restore: 이미 실행 중이면 확인; 부재 시 원 workspace의 소유 terminal create
      → verify: 실행 중 identity와 재시작 증거를 분리
    → 입력 전 atomic 로컬 기록 → 실제 접수/UUID/cwd/권한 확인 → 수행자가 결과 보고
```

`~/.local/state/tr-kit/session-restart`는 배포 트리 밖의 실행 시 생성물이다. 목록 조회만으로 만들지 않는다. machine/profile에 묶인 metadata 배치와 진행 기록, integrity key, lock을 0700/0600으로 보관한다. batch에 저장된 command를 실행하지 않으며 UUID로 제한된 native resume 문장만 현재 코드에서 구성한다. 업데이트 작업이 목록 보존을 포함하면 orca-update 수행자가 session 진입점으로 연결하며 업데이트·재연결/probe 정책을 복제하지 않는다.

native CLI 업데이트 연결은 session reference의 단일 계약이 소유하고, 실제 설치는 현재 호스트의 기존 공식 관리자가 수행한다. Python helper는 설치·계정/채널 전환을 실행하지 않는다. Orca 앱/runtime 업데이트는 기존 orca-update의 별도 책임이다.

`runtime_refresh.status`가 제한된 native resumeMode를 기록하고 `runtime_refresh.resume_command`가 두 관측 모드의 고정 argv를 구성한다. 기존 refresh와 session_restart의 restart/restore가 같은 함수를 호출한다. 미확인 모드는 exit/create 전에 수동 처리하며, mode 없는 부재 배치나 저장 command/flag/환경으로 옵션을 추정하지 않는다. raw command는 배치에 저장하지 않는다.

Codex의 headerless placeholder는 조회 조건이며 native 버전 증명이 아니다. fresh status에서 파싱한 known nativeVersion과 기존 native inventory의 현재 CLI 버전을 resume 전에 대조하고, 부재 restore도 create 직전 설치 snapshot을 확인한다. Claude project/local 설치 snapshot은 절대 projectPath를 검증한 context SHA256을 identity·정렬·installed_versions key에 사용하며 다른 프로젝트의 설치를 필터링하지 않는다. 같은 context 중복과 enabled 의존성 모호성은 계속 보류한다.

## 2026-11-20 hook 보완의 배치

Python stdin 오탐 보완은 기존 common/base/scripts/secret_guard.py 안의 검사 표현과 판별만 바꿨다. 제품 adapter·등록·적용 범위는 유지한다. 실제 흐름은 [후속 결정 기록](decisions/20261120-hook-bmad-native-validation.md)에 있으며 임시 native 검증 설정을 배포 구조로 채택한 것은 아니다. 당시 미결이던 private native 계약/패키징은 [다음 연결 검증](decisions/20261120-native-private-interface.md)에서 구현·격리 검증했다. 이후 수정한 후보 전체의 재패키징·통합은 별도로 남는다.

## 합의한 배치

| 위치 | 책임 |
| --- | --- |
| common/base | 공통 자체 지침·skill·실행 및 검사 로직 |
| adapters/codex, adapters/claude | 제품별 지침·실행·hook 등록·이벤트 입출력 차이 |
| scripts, tests | kit 자체 조립·검증·배포 도구와 시험 |
| docs | kit 요구·설계·결정·검증 추적 |

common/base는 adapters/codex처럼 영역/대상 계층을 맞추려던 명칭이다. base/common으로 변경하기로 하지 않았다. 이 표는 책임 배치이며 해당 디렉토리와 실행 파일을 모두 생성했다는 뜻은 아니다.

## 저작·감사 진입점의 논의 결과

plugin-authoring의 SKILL.md에 이 skill 사용 시 필요한 고유 공통 판단과 요청 분기를 둔다. 대상별 저작·감사는 references/{skill,hook,kit}/{authoring,audit}.md로 구분한다. 별도 common.md는 두지 않는다.

[SKILL.md](../common/base/skills/plugin-authoring/SKILL.md)와 조건부 공통 reference, skill·hook·kit 각각의 저작·감사 기준을 작성했다. 현재 실제 자체 지침은 10개이며, 작성 상태와 실제 행동 검증 범위는 verification.md에서 구분한다. 작성·감사 기준 본문을 docs에도 복제하지 않는다.

대상 여러 종류에서 재사용하되 조건이 성립할 때만 수행하는 상세 절차는 references/shared/ 아래로 분리했다.

| 작성된 자료 | 적용 조건의 구분 |
| --- | --- |
| structure-view.md | 구성 변경 또는 구성 설명·실제 연결의 감사 |
| reading-flow.md | 읽기·reference 선택·호출 흐름 변경 또는 해당 흐름 감사 |
| behavior-tests.md | 지침 신규 작성·의미·발동·선택·연결 변경, 행동 및 보존 검증 |

본문은 적용 조건과 읽을 시점을 명시한다. 조건부 분리를 선택 사항으로 해석하지 않는다. 항목화는 내용을 삭제하거나 표현을 넓히기 위한 축약이 아니라, 조건·예외·금지를 각각 확인할 수 있게 하기 위한 구성이다.

공통 검사 로직과 제품별 이벤트 연결 코드를 분리한다. 구현한 제품별 이벤트·입출력과 직접/native 시험은 [hook 검증](decisions/20261120-hook-bmad-native-validation.md)에 연결한다. 모든 도구·이벤트의 지원이나 미관측 입력까지 검증한 것은 아니다.

## plugin-authoring 내부 책임

명칭은 사용자가 plugin-authoring으로 확정했다. 내부 kit/은 kit 전체를 다루는 대상별 기준이며 진입점 이름과 구분한다.

| 위치 | 소유 책임 |
| --- | --- |
| SKILL.md | 요청 분기, 공통 요구·승인·외부 재사용·실패·완료 판단, 조건부 절차 적용 조건 |
| references/shared/ | 도표·읽기 흐름·행동 시험의 상세 수행 방법 |
| references/skill/authoring.md | skill 역할·발동·입출력·본문/reference 구성과 저작 도구 연결, skill 전용 관측점·감사 전달 자료 |
| references/skill/audit.md | 작성 기준에 연결된 증거·검사 방법·판정·발견 사항 보고. 기준 본문을 복제하거나 작성 절차를 재실행하지 않음 |
| references/hook/authoring.md·audit.md | hook 다섯 저작 기준과 실제 코드·등록·native/합성 시험 증거의 감사 |
| references/kit/authoring.md·audit.md | 전체 책임·의존·제품·자료·배포 연결의 저작과 구성 사이 관계 감사 |
| docs/verification.md | 작성 여부·미작성 대상·검증 상태. 실행 지침 안에 개발 진행 상태를 중복 관리하지 않음 |

skill 전용 reference가 공통 조건·승인·실패·재검증 절차를 다시 규정하지 않도록 수정했다. 이 작성 기준은 plugin-authoring 자신에게도 적용하며, 실제 적용·형식 확인과 행동 검증·감사 완료는 구분한다.

skill 작성 기준을 보강해 공통 목차·대안 분기·조건부 추가 표·연결 계약·지원 자료·수정 보존·제품별 대응·형식 검증을 구체화했다. 당시 다섯 자체 지침에 적용한 목차 규격을 이후 작성된 전체 10개에서도 확인했다. 외부 공식 원문에 대한 목차 강제와 기존 장식 기호 금지의 자동 채택은 하지 않는다.

도표는 물리적 파일 구조와 읽기·실행 흐름을 분리한다. 구조 트리의 자식은 실제 포함 관계이며, 참조 자료·판정·보고 결과를 파일처럼 섞지 않는다. 상세 표현 기준은 shared/structure-view.md가 소유하고 흐름 검사는 실제 대상·주체와의 일치를 확인한다.

### 현재 파일 구조

```text
plugin-authoring/
├── SKILL.md
└── references/
    ├── shared/
    │   ├── structure-view.md
    │   ├── reading-flow.md
    │   └── behavior-tests.md
    ├── skill/
    │   ├── authoring.md
    │   └── audit.md
    ├── hook/
    │   ├── authoring.md
    │   └── audit.md
    └── kit/
        ├── authoring.md
        └── audit.md
```

### 읽기·수행 흐름

```text
사용자 요청 → 수행자가 SKILL.md에서 대상·동작별 분기 선택
  → 대상의 authoring/audit 읽기
  → 조건에 맞는 shared 방법 적용
  → 수행자가 작성·검사·증거 대조
  → 공통 판정과 미검증 범위 보고
```

## 현재 남은 검증·결정

- 후보의 묶음·pin·격리 연결/영향 검증은 후속5번에서 수행했다. 운영 버전·manifest가 바뀌면 native pin과 private 묶음을 함께 다시 대조해야 하며 격리 검증을 실제 호스트 반영으로 확대하지 않는다.
- A-03 보완 뒤에도 남은 Claude 분량 위반과 기존 운영 hook의 명령 분류 차단. 새 후보 지침의 자연 발동·전체 업무·압축/재개 검증은 별도다.
- 운영 전환 대상·현재 설치/활성 상태 확인과 설치·trust·새 세션 반영. 실자료·기존 DB·백업/timer·capture의 실제 효과는 별도 승인·검증 범위다.
- 방법론 목록/PTBMAF·Design Doc, Obsidian·NotebookLM, README 전면 재작성 등의 후속 계획은 [이관 현황](migration-status.md)에 보존한다. 현재 필수 기능으로 자동 편입하지 않는다.

## 단계별 구조 이력 — 각 시점의 기록

아래 구조·흐름·수치와 미결은 각 단계 당시 기록이다. 후속 완료 여부는 위 현재 상태와 연결된 결정/검증을 따른다. 초기 구조 트리를 전체 최신 inventory로 해석하지 않는다.

### 외부 원문 보호 검사 — 2026-11-17

공통 후보 검사는 common/base/scripts/upstream_guard.py, 실제 현재 파일 검사는 upstream_artifacts.py가 소유한다. 제품별 payload와 응답 연결은 adapters/{codex,claude}/scripts/upstream_guard.py, deadline·응답 검증은 run_upstream_guard.sh가 맡는다. 각 제품의 hooks/upstream-guard.json.in은 비활성 등록 template다.

scripts/upstream-catalog.py는 명시 원본의 pin을 작성하고 render-upstream-hook.py는 명시 root·catalog·scope의 이벤트별 명령을 JSON으로 출력한다. check-upstream-artifacts.py는 조립·전송 직전 새 검사 진입점이며 실제 조립/전송기는 아니다. tests/test_upstream_guard.py와 test_upstream_lifecycle.py에서 직접·합성 연결을 시험한다.

물리적 배치와 실행 흐름, 검사 대상·상한·실패 계약·한계는 [현재 설계 기록](decisions/20261117-upstream-guard-pre-post.md)을 참조한다. 실제 제품 등록·trust·활성 조합과 전송기는 미연결이다. 자체 source 조립기의 연결은 아래 이관 항목을 참조한다. 기존 비밀·역할 검사를 대체하지 않는다.

### 시크릿·커밋 검사 추가 구성 — 당시 상태

[시크릿 hook 구조·흐름](decisions/20261117-secret-hook-implementation.md)에 실제 파일 배치와 호출 관계를 연결했다. common/base/scripts/secret_guard.py가 Gitleaks·Git 후보·literal 검사를, adapters/{codex,claude}/scripts/secret_guard.py가 제품 응답 변환을 맡는다. secret-tools.toml은 Gitleaks pin만 소유하며 외부 바이너리·원문을 동봉하지 않는다.

제품별 secret-guard.json.in과 두 renderer는 비활성 등록/script 출력이다. check-git-secrets.py는 실제 전송을 하지 않는 검사 CLI다. Git 기존 hook 관리자·체인·등록 lifecycle 이관과 실제 제품 설치·활성 조합은 미실행이며, 원문 보호 검사와 서로 다른 책임을 가진다.

### 1〜3 이관 후 source 구조 — 당시 발췌

```text
common/base/
├── instructions.md
├── workflow.md
├── skills/
│   ├── plugin-authoring/
│   ├── security-scan/
│   ├── profile-setup/
│   ├── project/
│   ├── session/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/runtime_refresh.py
│   ├── orca-cli/
│   ├── worktrunk/
│   └── orca-update/
└── scripts/
    ├── provider_links.py
    ├── security-tools.toml
    ├── secret-tools.toml
    ├── secret_guard.py
    ├── upstream_guard.py
    ├── upstream_artifacts.py
    └── run_upstream_guard.sh
adapters/
├── codex/
│   ├── AGENTS.md.template
│   ├── scripts/
│   └── hooks/
└── claude/
    ├── CLAUDE.md.template
    ├── scripts/
    └── hooks/
scripts/assemble.py
tests/
docs/
```

`hooks/`는 비활성 template이며 등록·활성화를 의미하지 않는다. 자체 source bundle에 공통 지침·workflow·자체 skill과 선택 adapter를 넣고 외부 entry는 metadata로만 기록한다. 설치 위치·자동 로드·native manifest를 확정한 배포 구조와는 구분한다. 상세 연결과 미이관 의존성은 [이번 결정](decisions/20261117-migration-1-3.md)을 참조한다.

### 4번 이관 당시 추가 구성

```text
common/base/
├── references/
│   └── external-connection.md
├── skills/
│   ├── bmad/
│   │   ├── SKILL.md
│   │   └── references/connection.md
│   ├── bmad-build/SKILL.md
│   ├── bmad-deep-recon/SKILL.md
│   ├── bmad-architecture/SKILL.md
│   ├── bmad-agent-po/SKILL.md
│   ├── find-docs/SKILL.md
│   ├── frontend-design/SKILL.md
│   └── playwright-cli/SKILL.md
└── scripts/
    ├── provider_links.py
    └── dev-tools.toml
```

위 트리는 추가 구성의 발췌다. BMAD 진입점은 실제28개이며 나머지 기존 자체8개는 유지한다. 전체39개 SKILL.md와 상세 목록은 실제 source·[이번 이관 기록](decisions/20261117-migration-4.md)에서 구분한다. bmod3개 metadata·외부 본문·bindings·runtime은 자체 source에 추가하지 않는다.

자체 source bundle에서도 common/base/skills·scripts·references 위치를 유지해 상대 참조를 보존한다. 앞선1〜3 단계의55개 파일은 당시 조립 결과이며, 상대 참조를 포함한 현재90개 조립 검사와 구분한다. 공식 설치와 제품 native manifest/초기 주입은 이후 통합 대상이다.

### 5번 이관 당시 추가 구성

공통 source에 doc-coauthoring·github-readme-generator·archify·diagram-design·artifact-publish의 자체 SKILL.md5개를 추가했다. 기존 업무 owner와 공식 외부 설치본의 책임을 유지하고 common/base/references/external-connection.md를 재사용한다. 전체 자체 skill은44개다.

게시의 공통 판단은 base에, Sites/native Artifact 차이는 adapters/{codex,claude}/skills/artifact-publish/references/provider.md에 둔다. 실제 제품으로 하나를 선택하며 reference 자동 합성/병합을 하지 않는다. assemble.py는 선택 제품의 자체 adapter/skills 경로만 보존한다.

전송 검사 진입점 scripts/check-artifact-secrets.py는 security-scan이 소유한 references/artifacts.md로 연결하며 기존 common/base/scripts/secret_guard.py의 scan을 호출한다. 일반 payload의 비밀 검사와 kit 외부 원문 gate는 별개다. 파일 트리·수행 흐름·공식 참조·한계는 [5번 기록](decisions/20261117-migration-5.md)에 있다.

### 6번 이관 당시 추가 구성

공통 source에 document·mem-search·wiki의 자체 진입점3개를 추가해 총47개다. document의 조건부 reference는 자료/기록 분기와 필요한 연결만 읽는다. 기존 업무별 문서 작성 owner·BMAD 작업 정본·경험 후보·Wiki 지식의 책임은 유지한다.

assets.py·git-excludes.py는 기존 자체 연결을 보완한 helper다. profile_config.py는 기존 profile-setup 규격의 순수 필드 검사를 공유하고 assets가 사용한다. 실제 sync 실행이나 소속/Git boundary 검증을 구현한 것은 아니다. 전역 제외/정확한 백업 예외는 profile-setup의 조건부 references/git-excludes.md가 소유한다.

Wiki의 의미/승인은 공통, 공식 제품 entry 차이는 adapters/{codex,claude}/skills/wiki/references/provider.md에 둔다. 조회는 공식 read-only wiki-query, 관리만 해당 제품 wiki/wiki-manager에 연결한다. 기존 bundled records.py·외부 binding/원문/runtime은 가져오지 않는다. 파일 구조와 읽기/실행 흐름·미이관은 [6번 기록](decisions/20261117-migration-6.md)에 구분했다.

### 7번 이관 당시 추가 구성

Android 구조·Wear Compose·테스트 전략·Compose 테스트 작성·instrumented runner 구성·ADB 실행의 자체 wrapper6개를 common/base/skills에 추가했다. 공통 scope/version/device/result 기준과 역할 선택은 common/base/references/android-work.md, 공식 연결은 기존 external-connection.md가 소유한다. 자체 skill은 총53개다.

bmad-build는 Android 전문 판단이 필요한 요청에서만 위 공통 기준으로 필요한 연결을 선택한다. 공식 build/전문 절차·작업 정본을 이중화하지 않고 이웃 skill6개를 일괄 로드하지 않는다. 원문·binding·예제·runtime을 kit에 포함하지 않는다. 같은 연결 본문을 양 제품 adapter에 복제하지 않았으며 실제 제품 지원은 공식 provider와 native 통합 검증 대상이다.

실제 파일 구조·읽기/실행 관계·보존한 경계·미확인은 [7번 기록](decisions/20261118-migration-7.md)에 있다. source 조립/fixture 검증과 실제 Android 도구·기기·설치/배포의 상태는 구분한다.

### G1 이후 Git 등록 연결

`common/base/scripts/git_guard_install.py`가 자체 등록·journal·상태/복귀와 hook 실행을 소유한다. 루트 `scripts/git-guard-install.py`는 명시 CLI이며 공통 `secret_guard.py`와 기존 `scripts/check-git-secrets.py`를 재사용한다. 제품 adapter에는 같은 관리기를 복제하지 않는다. 공식 Gitleaks는 외부 provision receipt와 hash로 연결하며 바이너리를 동봉하지 않는다.

`security-scan`의 Git 분기는 검사와 등록 요청을 구분하고 해당 reference만 읽는다. 등록 plan은 출력만 만들며 CLI apply는 reviewed plan_id를 대조한다. 안정 state에 자체 runtime/정책을 준비한 뒤 명시 effective Git hooks에 wrapper를 연결하는 구조다. pre-commit/pre-push는 등록 root 검사 → 기존 hook → 등록 root 재검사로 이어진다. 정상 상태의 공유 hooks를 쓰는 미등록 worktree는 기존 hook만 유지하며, 전체 runtime 의존이 깨졌을 때까지 비간섭을 보장하는 것은 아니다.

파일 트리·실행 흐름·정책/변경 경계는 [G1 기록](decisions/20261118-g1-git-enrollment.md)에, 실제 직접/모델/조립 시험과 미실행은 verification.md에 연결한다. 운영 hook·설치본은 이 source 구성과 별개이며 아직 전환하지 않았다.

### G2 이후 공식 도구 준비·검증

`common/base/scripts/toolchain.py`는 새 prefix의 공식 manager/release 연결·receipt·상태를, `toolchain_verify.py`는 버전 및 선택 local/network probe·자기 session cleanup을 소유한다. 루트 setup_dev_tools.py/setup_git_guard.py/verify_dev_tools.py는 얇은 CLI다. 설치와 semantic probe의 역할을 나눴고 완성 로직을 제품 adapter에 복제하지 않았다.

설치 버전 정본은 development의 dev-tools/security-tools와 Gitleaks의 secret-tools로 구분한다. Gitleaks-only group은 development pin을 필수로 읽거나 묶지 않는다. 기존 버전은 유지하고 이전 준비기에서 선택했던 Python Playwright1.64.1·Node 최소22.13.0 및 현재 TOML runner의 Python3.11 전제를 명시했다. source 작성 과정에서 실제 호스트 runtime을 바꾸지 않았다.

필요한 사용자 절차는 common/base/references/toolchain.md에서 소유하고, security-scan의 명시 도구 준비 요청에서만 조건부 연결한다. 일반 스캔·조회·plan에서 자동 설치하지 않는다. 공식 패키지/바이너리/browser는 실제 준비 시 source 밖 prefix에 설치하며 kit source/조립물에 포함하지 않는다. 파일 트리·실행 흐름·한계는 [G2 기록](decisions/20261118-g2-toolchain.md)에 있다.

### G3 이후 선언 읽기량 측정

common/base/scripts/context_check.py는 기존 자체 정적 측정기를 새 source/보존 경로에 맞춘 공통 로직이고, scripts/context_check.py는 진입 CLI다. scripts/context-cases.json은 자체 source의 부분 경로5개를 선언한 예제이며 실행할 실제 작업의 필수 읽기를 자동 선택하는 규칙이 아니다. 제품 adapter에는 측정 로직을 복제하지 않는다.

plugin-authoring의 조건부 shared/reading-flow.md가 측정의 사용법·범위·판정 의미를 소유한다. 지정된 roots/cases만 읽으며 hook·상시 수집·tokenizer·비용 추정기·자동 코드 축약은 추가하지 않았다. 측정 모드와 기존 비증가 비교를 분리하고 canonical 파일의 전체/절 겹침을 source hash와 함께 집계한다. 파일 트리와 실행/판정 흐름·제약은 [G3 기록](decisions/20261118-g3-context-check.md)에 연결한다.

### G4 이후 공식 memory 실행기 연결

common/base/scripts/claude_mem.py는 provider_links와 toolchain의 명시 entry/runtime 확인을 재사용하고, root scripts/claude-mem.py가 진입한다. 공통 references/claude-mem.md가 연결·수명 관리 절차를 소유한다. mem-search/document는 별도 관리 요청에만 이 안내로 연결하며 검색 정책·공식 workflow를 가져오지 않는다.

### G5 이후 제품 포장과 격리 수명 관리

기존 assemble.py의 source-bundle-v1과 fresh 검사를 보존하고 native 분기에서 package.py가 제품 manifest/marketplace·hook 등록·현재 파일 명세를 추가한다. skill/reference는 common/base 경로를 유지한다. 공통 초기 지침과 upstream binding relay는 common/base/scripts/plugin_runtime.py, native 등록 형식은 adapters/<product>, package/lifecycle/CI 도구는 root scripts가 소유한다. 외부 기능·runtime은 동봉하지 않는다.

source 작성→raw source 조립→native 구조 생성→현재 package 검사→정적 설치 계획→apply 전 scanner→격리 official manager→cache byte 대조의 단계다. review/guarded·초기 지침 전달·실제 native trust/callback·G4 MCP/공식 providers·private 통합을 서로 다른 상태로 관리한다. 세부 트리와 변경 이유는 [G5 기록](decisions/20261118-g5-packaging.md), 실제 절차는 root INSTALL.md, 검증 범위는 verification.md가 소유한다.

양 adapter의 mcp/*.in은 native 형식 출력 원문이며 조립에서도 제품별 상대경로를 보존한다. render는 stdout 출력만 하고 native 등록은 수행하지 않는다. 외부 worker/MCP는 source 밖 명시 설치본을 직접 실행한다. source별 책임과 전후 트리·실행 흐름은 [G4 기록](decisions/20261118-g4-claude-mem.md)에 있다. 현재 native 설치·기존 개인 DB 연결은 미실행이며 자동 인수 기능은 없다.

### G7 이후 설치 리소스·제품 검수

provider_links는 기존 entry 선택/검사를 유지하고, provider_review는 명시 설치 디렉토리 전체 명세·설치 근거 hash·제품 검수 기록의 현재 일치와 업데이트 차이만 검사한다. root scripts/provider-review.py가 CLI이며 외부 연결 안내에서 실제 수행 시 조건부로 연결한다. 상시 hook·별도 daemon·설치기는 추가하지 않았다. 로컬 검수 기록의 fresh 일치와 공식 provenance 인증·native/모델 실행을 구분한다.

2026-11-20의1번 검증에서는 source 밖 공식 설치본을 준비했다. own toolchain_verify의 합성 browser fixture만 임시 loopback HTTP로 제공하고 종료한다. own claude_mem은 schema2의 선택 claude_bin으로 검증한 CLI 디렉토리만 격리 PATH에 추가한다. 신규 skill/hook·상시 서버·운영 초기 설정은 추가하지 않았다. 아래 source/외부 연결은 후속 공식 원문 catalog 채택 승인 뒤 새 공통/private source 조립·pin 대조를 진행했다. 운영 초기 설정과 native 검증은 별도다.

```text
common/base/scripts (own)
  provider_links / provider_review ──검사──> source 밖 공식 설치본·검수 기록
  toolchain_verify ──시험──> 공식 CLI/브라우저 + 합성 loopback 문서 (종료)
  claude_mem ──실행──> 명시 Node/Bun + 선택 claude_bin → 공식 MCP/worker (종료)
```

Claude-Mem은 schema2 binding의 두 review를 plan hash에 묶고 start/MCP 전에 재검사한다. 검수 부재/리소스 변동 시 신규 실행 전에 보류하며 기존 소유 worker의 stop은 별도 소유 검사로 유지한다. private common_links가 같은 공통 검사 CLI를 호출하며 구현을 복사하지 않는다. private source pin은 검토한150파일 source-bundle-v1이고 native 포장과 분리한다. 구조와 지원 현황·미결은 [G7 결정](decisions/20261118-g7-provider-review.md)과 [provider 현황](provider-status.md)에 연결한다.
