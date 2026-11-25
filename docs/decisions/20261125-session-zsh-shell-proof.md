# NAS zsh 정상 종료 뒤 빈 shell 증명

## 요구와 결정

승인 계획 `plan-zsh-shell-restart-proof.md`(2026-11-25)는 NAS 원래 창을 종료하기 전에 P10k의 standalone `❯` 복귀 경로를 검증하도록 한정했다. 기존 absolute cwd `$`/`#` 판정에 glyph만 추가하면 native/REPL과 구분할 수 없어, 실제 local process 증명과 기존 fresh same-UUID 정상 종료 안내를 함께 요구한다. 원 signed Stores·실패·선택·수동 예외를 유지하고 general missing-state admission, trust DB·global shell/profile/role 변경이나 새 bypass를 허용하지 않는다.

기존 `runtime_refresh.py`의 management stat/executable 판독을 공통 함수로 추출하며 caller-helper 의미는 유지한다. 별도 target zsh 증명을 client 메모리에 고정하고 exact-resume durable 기록 전후에 같은 shell/Orca/설치 가드를 대조한다. `session_restart.execute`와 `runtime_refresh.apply`는 invocation 시작에서 과거 ephemeral 증명을 지운다. 새 실행기·skill·hook·설정·Store schema/history migration은 없다. 실제 구성은 [구조](../architecture.md#nas-zsh-빈-shell-증명--2026-11-25), 세부 판정의 정본은 [공통 실행 계약](../../common/base/skills/session/references/runtime-refresh.md#정상-종료-뒤-nas-zsh-빈-shell-증명)이다.

## 검증과 한계

두 session suite의 합성 proc/transport와 실제 소유 PTY 시험은 process identity·foreground·cwd/pane·실행 파일·중복·drift·durable 전후 거부와 한 번의 resume/생성0을 확인한다. 로컬 zsh 부재 시 실제 PTY는 bash의 미지원 거부만 확인하며, modeled zsh 성공을 native zsh 성공으로 확대하지 않는다. 실제 시험 수·공통 CI·검수와 미실행 운영 범위는 [검증 기록](../verification.md#nas-zsh-빈-shell-증명--2026-11-25)을 따른다.

proc와 Orca 관측 및 기록·입력은 원자적이지 않다. 동일 UID의 악의적 process가 만든 증거를 방어하는 보안 경계도 아니다. 증명 실패는 exact resume 전에 중단하고 이미 durable 기록한 sending은 기존 uncertain 원칙으로 남긴다. 실제 NAS 소유 canary의 exact UUID/cwd/Full Access/mode 종료·재개 두 번, 원래 배치 복구·native hook trust·private pin/package·배포는 source 시험과 별도로 확인해야 한다. company inno common-only, dev01 root conversation 제외와 PC reboot 금지를 유지하며 plugin consumption은 독립 증거 없으면 unverified/null이다.
