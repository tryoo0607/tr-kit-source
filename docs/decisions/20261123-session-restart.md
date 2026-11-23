# 재부팅 대비 세션 재시작 배치

## 요청과 결정

사용자는 재부팅 전에 열린 세션의 재개 목록을 보존하고, 후속 요청에서 같은 대화를 복원하며, 예외와 호출자 세션을 수동 재시작 목록으로 확인하기를 요청했다. 승인 계획은 로컬 `_bmad-output/plan-session-restart-batches.md`, 기준 revision은 `55c4498e274ea5fbf6199878c3e9ed339c2e89c6`이다. 후속으로 native CLI 업데이트 연결과 **실제로 확인된 기존 권한 옵션의 보존**을 승인했다. 일반 세션의 권한 확대·전역 설정 변경을 허용한 것은 아니다.

기존 session/runtime-refresh와 공식 Orca·native CLI를 재사용한다. 재부팅 뒤 읽어야 하는 배치는 유효기간 5분인 runtime-refresh 계획과 분리한다. 실제 호스트 배포·Orca 업데이트·운영 세션 재시작은 이번 배포 전 준비의 완료 범위와 구분한다.

## 구성과 보존

- `session_restart.py`가 prepare/list/restart/restore/verify와 호스트 로컬 배치를 소유한다. runtime_refresh의 inventory·guard·native status·고정 resume 구성기를 공유한다. [실제 구성과 호출 흐름](../architecture.md#세션-재시작-배치)을 따른다.
- prepare는 선택·예외/self를 먼저 보존하고, 안전한 선택에만 새 status를 조회한다. 종료하지 않으며 예외/self에는 status도 보내지 않는다. 결과에는 host/workspace/provider/tab/leaf/가능한 UUID와 수동 사유를 표시한다. 관리 shell은 native 수동 목록과 구분한다.
- state는 Linux machine/profile에 묶고 0700/0600, descriptor 고정·symlink/hardlink 거부, signed atomic replace/fsync·flock을 사용한다. 서명은 우발 수정 검출이며 같은 계정 소유자를 막는 보안 경계는 아니다. list는 저장소를 만들지 않는다. 대화·화면·인증·실행 command를 배치에 넣지 않는다.
- 모든 입력/launch 전에 durable sending을 기록하고 receipt를 따로 보존한다. 첫 실패 뒤 나머지는 보류한다. 불명확한 실행은 자동 재전송·새 batch·중복 terminal로 해결하지 않는다. 별도 verify가 이전 정상 종료 또는 소유 terminal 근거와 새 UUID/cwd/권한을 함께 대조한다.
- runtime 경계 뒤 list/ps/show/read로 다시 찾는다. 같은 workspace의 선택 후보는 안전한 pane에만 새 status를 보내 UUID로 구분한다. 예외·미선택·ps에만 남은 agent·중복 UUID·미확인 child가 부재 판정을 막는 가드를 유지한다.
- 설치 metadata, 접수, 새 native 프로세스의 UUID/cwd/권한과 실제 플러그인 소비를 분리한다. `consumption=unverified`, `consumedVersion=null`이다. private 역할·profile·base 설정·기존 cache와 개인 데이터 연결은 변경하지 않는다.

## 권한 보존과 제품 차이

현재 자동 재개는 관측된 Codex0.167.1/0.167.2/0.171.0 Full Access와 Claude2.1.330 bypass 모드로 제한한다. fresh native 상태와 현재 설치 버전을 대조하고, 단일 구성기가 exact UUID와 승인된 고정 옵션만 만든다. 저장 command/flags/환경은 재생하지 않는다. default/Custom/unknown·부재 legacy는 exit/create 전에 수동으로 남긴다. 기존 uncertain 시도가 우선 보존된다.

Codex restart는 새 identity → 정상 exit와 새 stream의 같은 UUID 종료 안내 → 현재 빈 shell → exact resume → 새 identity 대조다. restore는 부재를 확인한 뒤 공식 terminal create를 사용한다. Claude restore도 같은 UUID와 관측된 권한을 보존하지만, **Claude 즉시 restart의 자동 종료·shell 전이는 미지원으로 수동**이다. native clean exit 관측을 helper 자동 지원으로 확대하지 않는다.

신규 소유 terminal/resume 직후의 기존 10초 readiness 안에서 agent/child identity unknown만 입력 없이 다시 조회한다. Claude status 전에는 권한 표시를 최대3초/12회 기다린다. 매번 full guard를 적용하며 draft/busy/trust/실제 child 등은 즉시 중단한다. 기다림만으로 권한을 추정하거나 가드를 생략하지 않는다.

Claude 설치 목록은 공식 [JSON 계약](https://code.claude.com/docs/en/plugins/cli-reference#json-output)의 설치 단위와 project/local `projectPath`를 반영한다. 검증한 절대 경로의 SHA256을 context identity로 사용하고 전체 설치를 유지한다. 다른 프로젝트의 disabled 동일 ID를 삭제·cwd 필터링하지 않으며, 같은 context 중복·경로 미확인·enabled 의존성 모호성은 계속 거부한다.

## 실제 발견과 보완

| 관측 | 반영과 보존 |
| --- | --- |
| 초기 Codex Full Access의 bare resume 뒤 UUID/cwd는 같으나 Custom으로 권한 변경 | 원래 실패 배치를 유지. 사용자 추가 승인 뒤 관측 모드의 고정 옵션만 지원하고 미확인 모드는 사전 수동 처리 |
| native CLI가 허용한 옵션-before-UUID를 Orca send가 ownership 오류로 거부 | 소유 진단에서 UUID→고정 옵션의 접수·동일 identity를 확인해 canonical 순서 사용. request 조회 부재를 미실행 증명으로 삼아 재전송하지 않음 |
| Codex header scroll-out 뒤 placeholder가 draft로 오인됨 | 실제 idle/typed/clear 계약으로 exact placeholder와 빈 draft의 조회만 허용. 보이는 unknown header·실제 입력 draft는 계속 거부. fresh status로 버전을 따로 확인 |
| Claude 설치8건 중 다른 프로젝트 disabled 동일 ID가 모호성으로 거부됨 | 공식 context 계약으로 전체 목록을 보존하면서 identity를 구분. 설치/설정 변경 없음 |
| 신규 terminal 직후 child identity 미확인, 후속 explicit verify 성공 | 실패·별도 verify를 유지. 기존 readiness 범위에서 transient unknown만 재조회하며 일반 locate/부재 guard는 완화하지 않음 |
| Claude cold restore에서 권한 표시 미확인 | 초기 시차 가설과 달리 실제 spy가 `bypass permissions on (shift+tab to cycle) · ← for agents` 표시와 v2.1.330 header를 관측. 관측한 형식만 제한 지원하며 후속 시험 결과는 verification에 기록 |

원시 실행 증거와 실패 배치는 `/data/projects/_scratch/tr-kit-session-restart-20261123`에 별도 보관하며 Git·배포물에 넣지 않는다. 초기 실패와 후속 성공은 같은 시험으로 합치지 않는다. CLI 상세 error/request ID가 journal에 충분히 보존되지 않는 한계는 남기며 광범위 logging을 추가하지 않았다.

## 저작·검수와 남은 한계

plugin-authoring의 skill 작성·감사 및 구조/읽기/행동 기준, 공식 system skill-creator, BMAD build와 독립 quick review를 적용했다. 외부 원문·바이너리를 kit 구성요소로 복제·변형하지 않았다. 실제 실행과 정적·transport double·새 모델 시험은 [검증 기록](../verification.md#재시작-배치-배포-전-검수--2026-11-23)에서 구분한다.

실제 OS reboot, Linux 이외 플랫폼·다른 인증 계정/managed 환경, 자동 임계치 압축과 모든 skill의 실제 업무 성공은 이번 시험에 포함하지 않는다. 비원자적인 조회→입력·부재→launch 사이 외부 조작 경합과 미추적 작업 부재까지 보장하지 않는다. runtime 경계 뒤 같은 workspace의 예외 UUID가 불명이면 수동 확인이 필요하다.

후속 운영은 nas-vm → inno-desktop Claude 준비 → 사용자 reboot 뒤 해당 로컬의 복원 요청 → dev01 순서다. dev01의 현재 요청 대화는 수동 예외로 남긴다. native CLI·Orca 업데이트와 재시작은 각각 결과를 검증하며, 이 문서는 호스트 운영 완료 증거가 아니다.
