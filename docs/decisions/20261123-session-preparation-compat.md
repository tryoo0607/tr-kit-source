# 접수된 status만 있는 중단 준비의 명시 검증

R-52의 승인 계획은 `_bmad-output/plan-nas-session-preparation-compat.md`다. baseline은 `97da09a5faa04f226d38fae689d2cd32749b8d1d`이며 지정된 격리 worktree에서 공통 session helper·시험·계약과 추적 문서만 변경한다. 원격 실행·업데이트·권한/계정/config 변경·commit/push·패키징은 구현 범위가 아니다.

## 근거와 결정

계획에는 NAS Codex0.167.2가 한 번 접수한 `/status`의 응답이 최초 읽기 뒤 도착했고 cwd가 `~/projects/local/general`로 표시됐다는 관측이 있다. root가 전달한 약0.59초 도착 관측은 대기 fixture의 입력으로 사용했다. 구현자는 실제 NAS 응답이나 native 복구를 재관측하지 않았다. baseline source의 Codex native_query는 응답을 한 번만 읽었고 status는 비절대 cwd를 거부했으며, execute는 미완료 prepareState를 모두 거부했다.

공통 `runtime_refresh.py`의 passive_guard/current_status_response/finish_response/output_proof를 재사용한다. 지연·부분 status는 원 cursor로 bounded 관측하며 stream과 현재 frame의 metadata 및 확인한 frame proof가 일치해야 한다. 수신자 `Path.home()`에만 엄격한 home 표시를 연결하고 원 workspace와 exact 비교한다. 상한·입력 문법의 정본은 [runtime-refresh 계약](../../common/base/skills/session/references/runtime-refresh.md#codex-status-응답-대기와-수신자-home)에 둔다.

`session_restart.py`의 기존 signed Store/Recorder/binding/check_other_attempts와 fingerprint를 재사용한다. 명시 verify에서만 모든 과거 입력이 짝이 맞는 접수된 status인지 확인한 뒤, 원 queried 대상 중 native가 비어 있는 행에만 새 guarded status를 보낸다. identity 저장 뒤 최종 outcome 전에 중단된 경우에는 queried 행의 저장된 신원과 fresh 신원을 대조해 완료한다. 일반 locate·다른 terminal 추적은 사용하지 않는다. old failure/event와 untouched/manual 행을 보존하고 같은 배치에 준비 검증 결과와 응답 proof를 추가한다. 자세한 허용·거부·모달 제한은 [중단 준비 검증 계약](../../common/base/skills/session/references/session-restart.md#접수된-조회만-있는-준비-검증)에만 둔다. consumption은 계속 unverified이며 소비 버전은 null이다.

역할·파일 배치·의존성과 업데이트 순서는 바꾸지 않는다. 공통은 private나 특정 호스트 ID를 알지 않으며 새로운 관리 계층·외부 원문 사본도 추가하지 않는다. 기존 외부 Orca CLI와 제품 CLI를 부르는 자체 연결의 미충족 부분만 보완한다.

## 검증과 한계

[검증 기록](../verification.md#중단된-status-준비-호환성--2026-11-23)에 정확한 실행 수와 원본 위치를 둔다. 새 사례는 transport doubles와 실제 tempfile signed Store를 사용한다. 약0.59초 지연은 가상 시계로 재현하므로 native 시간 측정이 아니다. 기존 session 회귀의 소유 subprocess/CLI fixture 결과와 실제 제품·수신자 실행을 구분한다.

원자적인 terminal compare-and-send API는 추가하지 않았다. 마지막 passive 관측과 durable 기록·입력 사이 외부 조작 경합은 남는다. 접수 유실·unsafe 상태는 자동 복구하지 않으며, 조회 전용 verify에서 Claude 모달을 새로 열면 자동 키 입력 없이 남을 수 있다. 실제 NAS verify, 전체 CI/실제 Gitleaks8.30.1, 독립 review, pin·패키지·게시·rollout은 root의 후속 범위다.
