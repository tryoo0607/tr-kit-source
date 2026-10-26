# 코드 공간 구조와 배치

repo/group/workspace 관계와 코드 공간 배치를 판단할 때 필요한 절만 읽는다. 설정 필드와 문서 내부 구조를 이 파일에서 복제하지 않는다.

## 입력과 전제

확인된 코드 루트, repo 경로, 관리 등록과 요청 범위를 사용한다. 실제 경로와 설정/등록이 다르면 어느 쪽도 자동 덮어쓰지 않는다.

## 수행 방법과 절차

### 대상과 관계

| 개념 | 의미 |
|---|---|
| repo | Git 저장소. remote URL만으로 로컬 checkout 경로를 확정하지 않음 |
| project | 관리 대상 repo의 식별 단위. 여러 workspace가 같은 project에 속할 수 있음 |
| group | 관련 project의 선택적 논리 묶음. 상위 폴더명과 자동 동일시하지 않음 |
| checkout | 실제 파일이 있는 Git 작업 트리. bare 저장소는 코드 작업 checkout이 아님 |
| worktree | 같은 Git 저장소에 연결된 추가 작업 트리 |
| workspace | 도구가 관리하는 작업 공간. worktree인지 독립 clone인지는 실제 결과로 확인 |

### 신규 배치 기준

허용 배치 예시는 다음과 같다. 예시는 경로를 자동 생성하는 규칙이 아니다.

```text
<code-root>/<project>/
<code-root>/<group>/<project>/
```

기존 등록과 실제 checkout이 있으면 그 위치를 우선 유지한다. 신규 공간은 사용자가 지정한 위치나 관리 도구의 확인된 설정을 우선한다. 선택이 정해져 있지 않으면 단독 project는 직접 배치, 함께 배치할 group 요청이 있으면 group 하위 배치를 제안하고 생성 전에 대상 경로를 확정한다. group만 등록한 것은 물리 이동 지시가 아니다.

code-root는 설정의 확인된 값을 쓰며 repo 경로는 명시 연결과 관리 결과로 확인한다. [설정 규격의 경로 해석](../../profile-setup/references/config-schema.md#경로와-식별자-해석)은 조회 자료로 필요한 부분만 적용한다. 코드 경로 설정 작성/검증은 본문의 설정 연결 분기로 처리한다.

### workspace 기준

기존 checkout에서 읽기·논의를 진행할 수 있다. 독립 변경을 병행해야 하면 대상 repo, 시작 ref와 변경 격리 필요를 확인한 뒤 추가 workspace를 요청한다. workspace 실제 경로와 생성 방식은 도구 결과를 확인한다. worktree와 clone을 혼동하거나 임의의 고정 하위 폴더를 만들어 도구 등록을 대신하지 않는다.

공간 조작 도구의 선택과 연결은 [프로젝트 관리](management.md)의 계약을 따른다. 다른 개발 지침에서 이미 공간을 준비했으면 확인된 경로를 재사용한다.

### 임시 프로젝트와 정식 전환

임시 프로젝트도 로컬 Git repo로 시작한다. 기본 배치안은 `<code-root>/_scratch/<project>/`이며 정식 위치는 기존 신규 배치 기준을 따른다. code-root와 실제 대상 경로를 먼저 확인하고 전역 설정이나 기존 repo 위치를 자동으로 바꾸지 않는다. 로컬 Git 시작이 원격 저장소 생성이나 push를 뜻하지 않는다.

정식 전환은 같은 repo와 이력을 유지해 확정된 정식 위치로 옮기는 방식을 기본으로 한다. 최초 repo 생성과 원본 경로 이동은 Git 및 파일 조작 절차이며 Worktrunk가 전체 이관을 대신하지 않는다. 연결된 worktree와 Orca 등록이 있으면 이동 전후 연결 검증이 필요하다. 이력이 없는 빈 repo에서는 worktree 생성에 필요한 시작 commit부터 확인한다.

worktree 배치안은 원본 repo 옆의 `<project>.worktrees/<branch>/`다. `group/project`의 기존 부모 위치를 기준으로 하므로 group을 별도 템플릿 변수로 만들지 않는다. 구조 검토만이면 이 기준으로 충분하며 실제 생성이나 설정 확인이 필요할 때 management에서 선택한 도구 연결을 읽는다.

이 배치의 Worktrunk 템플릿은 `{{ repo_path }}/../{{ repo }}.worktrees/{{ branch | sanitize }}`다. `feature/login`은 경로에서 `feature-login`으로 구분된다. 실제 유효 설정, 경로 충돌과 설정 변경 승인을 확인한 후 wrapper에 전달하며 사용자 전역 설정을 자동 덮어쓰지 않는다.

### 문서와 assets 연결

코드 공간과 문서/assets 공간은 별도다. project는 확인된 project/group 식별자, 호스트와 코드 경로를 제공한다. 문서 위치 해석은 설정 규격, 내부 기록과 지식 연결은 document와 채택한 외부 도구가 소유한다. 코드 group 하위 배치를 문서 group 상속으로 해석하지 않는다.

## 결과와 완료 판단

대상 관계, 기존 또는 신규 배치 근거, workspace 실제 유형과 경로, 설정 충돌과 미확인 범위를 설명할 수 있어야 한다. 구조 검토 완료는 실제 생성 완료가 아니다.

## 실패와 복구

경로 충돌, 중복 등록이나 불명확한 소속은 해당 변경 전 확인한다. 기존 경로를 이동하거나 별도 checkout을 자동 생성해 충돌을 숨기지 않는다.
