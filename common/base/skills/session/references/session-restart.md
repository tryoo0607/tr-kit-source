# 재부팅 대비 세션 재시작 배치

## 목적과 역할 경계

재시작할 native 대화의 UUID와 선택·예외를 호스트 로컬 배치에 보존하고, 요청 범위에 포함된 Codex/Claude CLI 자체 업데이트를 기존 공식 관리자에 연결한다. 준비는 종료 승인이 아니며 재시작·재부팅 후 복원은 나중의 명시 요청에서 실행한다. Orca 앱/runtime 업데이트의 설치·버전·재연결·probe 검증은 orca-update가 소유하며 native CLI 자체 업데이트와 별도로 판정한다. 기존 runtime-refresh의 5분짜리 계획은 이 배치를 대신하지 않는다.

## 입력과 전제

대상 호스트에서 기존 Linux 계정과 native config 환경으로 실행한다. 선택할 현재 terminal handle과 입력을 받지 않을 예외 handle, 요청 세션의 `ORCA_PANE_KEY`가 필요하다. 자신을 유일하게 찾지 못하거나 원격 환경·다른 machine/profile이면 보류한다. 다른 호스트의 기존 수신자에게 전달할 때는 session 본문의 위임 분기를 사용하고 수신자가 자기 호스트 가드를 확인한다.

배치의 machine/profile은 machine-id의 hash, uid, home, Codex/Claude config 경로와 Orca profile/dev 환경에 묶인다. 인증정보는 읽거나 저장하지 않는다. 이 값은 native 로그인 계정의 인증 증명이 아니다. 별도 managed account, 계정 전환 또는 launch 환경이 원래 계정과 다르다는 징후가 있으면 자동 복원하지 않는다. Windows/macOS와 미확인 계정 계약은 보류한다.

## 수행 방법과 절차

1. 현재 skill의 `scripts/session_restart.py`를 Python 3으로 실행한다. `prepare --target <handle> [--target <handle> ...] [--exclude <handle> ...]`는 선택 목록·예외와 호출자의 native 세션을 먼저 저장하고, 안전한 선택 대상에만 새 `/status`를 보내 UUID/cwd/권한을 채운다. `/exit`·resume은 보내지 않는다. 명시 예외와 self는 상태 입력도 받지 않는다. 관리용 shell은 native 수동 재시작 대상으로 표시하지 않는다. 준비 중 첫 실패 뒤 나머지 상태 입력도 멈춘다.
2. 출력 `batchId`를 보존한다. `list [--batch <UUID>]`는 runtime 또는 대화를 열지 않고 저장 목록을 읽는다. 기록이 없으면 빈 목록이며 디렉터리·key를 만들지 않는다. 준비된 UUID, ready/deferred 및 수동 대상의 host/workspace/provider/tab/leaf/가능한 sessionId/사유를 확인한다. 예외의 UUID가 불명이면 null을 유지하고 추측하지 않는다. 업데이트 전에 전체 선택과 UUID가 보존된 배치를 확보하고 미확인 대상을 해소하거나 명시 예외로 둔다.
3. native CLI 업데이트가 승인된 경우에만 아래 제품 관리자 연결을 적용한다. 준비한 batchId/UUID/예외를 보존하고, 대상 호스트의 실제 실행 파일·버전·설치 방식·계정·채널을 확인해 같은 공식 관리자와 승인 범위를 사용한다. 이미 승인된 대상·효과는 다시 묻지 않으며, 목록 준비나 Orca 업데이트 요청만으로 native CLI 자동 업데이트를 시작하지 않는다. 실행 중인 기존 세션을 종료하거나 config·계정·권한을 바꿔 설치를 통과시키지 않는다. 설치 뒤 실제 실행 버전과 원 workspace의 소유 resume canary를 확인하고, 설치 성공과 기존 세션의 실행 버전·재개 성공을 구분한다. 이 Python helper는 제품 설치를 실행하지 않는다.
4. 나중의 실행 요청에서 `restart --batch <UUID>` 또는 재부팅 뒤 `restore --batch <UUID>`를 실행한다. 공통 `runtime_refresh.resume_command`는 native status의 정확한 권한과 제한된 `resumeMode`를 대조한다. 현재 자동 지원은 fresh status의 Codex0.167.1/0.167.2/0.171.0 `Full Access`와 관측 native Claude2.1.319/329/330/331 `bypass permissions` 두 기존 모드뿐이다. Claude launch 버전은 별도로330/331만 허용한다. 새 resume 전에는 현재 설치된 CLI 버전도 해당 launch 지원 범위인지 기존 native inventory로 대조하며, 부재 대상은 create 직전 설치 snapshot도 재확인한다. 이미 관측한 같은 권한을 보존하도록 사용자가 승인한 고정 옵션만 구성한다. default/Custom을 현재 config 기본값과 같다고 추정하지 않으며, 별도 보존 근거가 없는 모드는 exit/create 전에 `manual-restart-required`와 사유로 보류한다. 과거 배치의 mode가 없으면 부재 세션의 옵션을 추측하지 않는다. 아래 [명시 복구](#접수된-claude-준비의-명시-복구)의 일치하는 fresh attestation만 별도 보존 근거로 사용할 수 있다. 살아 있는 과거 대상은 UUID/cwd/권한이 같은 새 native status에서 모드가 확인된 경우에만 재시작한다. 기존 uncertain 시도는 먼저 차단·보존한다. 저장된 handle·PTY·shell 확인을 재사용하지 않고 현재 list/ps/show/screen으로 다시 찾는다. self/busy/draft/approval/child/unknown 가드는 입력 직전마다 유지한다. 같은 workspace의 여러 선택 세션은 안전한 선택 pane들에 한해서 새 `/status`의 UUID로 구분한다. 선택하지 않은 후보, 중복 UUID, 미확인 foreground·예외의 이동 가능성은 입력 또는 launch 없이 보류한다. runtime이 바뀐 뒤 같은 workspace의 예외 UUID가 불명이면 해당 workspace 복원은 보수적으로 보류할 수 있다.
5. `restart`의 Codex는 새 native identity와 모드 대조 후 `/exit`를 보내고, 그 직전 cursor 이후 같은 UUID의 정상 종료 안내와 현재 빈 shell을 확인한 경우에만 공통 구성기의 명령을 보낸다. 이미 Full Access인 세션의 예시는 `codex resume <exact UUID> --dangerously-bypass-approvals-and-sandbox`이며, 다른 세션을 Full Access로 올리는 승인이 아니다. 다시 UUID/cwd/권한과 기록된 모드를 확인한다. Claude native 종료/재개는 소유 canary에서 관측했지만 helper의 즉시 종료·shell 전이 자동 검증은 아직 지원하지 않으므로 즉시 재시작은 수동이며 `/exit`를 보내지 않는다. reload 성공을 restart 성공으로 바꾸지 않는다.
6. `restore`는 같은 UUID가 실행 중이면 검증 후 `already-running`으로 보고하며 재실행하지 않는다. 부재가 확인되면 기록된 모드와 현재 원 workspace/host를 다시 확인하고 공식 `terminal create --worktree id:<원 workspace ID> --command <공통 구성기의 exact resume>`로 소유 복원 터미널을 만든다. 지원된 native bypass와 launch 버전이 확인된 Claude 세션의 예시는 `claude --dangerously-skip-permissions --resume <UUID>`이며, 다른 권한 모드의 세션에 이 옵션을 붙이지 않는다. 임의 저장 command/flag/환경은 재생하지 않고 두 모드의 고정 argv만 사용한다. sparse create receipt의 handle을 새 show/list로 대조하고 idle·새 native status까지 확인한다. 오래된 shell에 입력하지 않는다. receipt가 불명확하면 부분 launch로 멈추며 다시 만들지 않는다.
7. `verify --batch <UUID>`는 launch/exit 없이 현재 native identity를 다시 확인한다. 불완전 준비는 아래 [접수된 조회만 있는 준비 검증](#접수된-조회만-있는-준비-검증)의 제한을 적용한다. 이전 정상 종료 또는 소유 터미널 근거가 없는 같은 live UUID는 원래 프로세스일 수 있으므로 restart 완료로 처리하지 않는다. `live-identity-confirmed-restart-unproven`은 실행 중 identity만 확인한 상태다. 이 경우 이후의 명시 `restart` 요청은 새 가드를 거쳐 실행하며, 완료된 재시작으로 건너뛰지 않는다. 확인되지 않은 시도는 자동 재전송하지 않는다.

부재 restore는 마지막으로 느린 설치 조회를 마친 뒤 fresh local list/ps로 runtime·유일한 self·원 workspace ID/path/host·terminal fingerprint/접근/provider/대기·agent/main/program/child 상태와 후보 집합을 다시 대조한다. 미선택 native/unknown 후보는 show/screen/status로 조사하지 않고 보류한다. 다른 선택 세션은 실제 새 `/status` 응답을 검증할 때 사용한 frame의 cursor와 화면 SHA256을 그 응답의 증거로 유지한다. 마지막 조회 뒤 선택 pane을 passive 관측해 증거와 같아야 하며, 같은 pane/fingerprint/state라도 UUID·출력·cursor가 바뀌거나 증거가 없으면 create 없이 중단한다. status 뒤 별도 cursor baseline을 얻어 대체하지 않는다. 응답을 기다리는 동안에는 긴 설치 조회를 추가하지 않으며, 신원은 [공통 status 응답 계약](runtime-refresh.md#codex-status-응답-대기와-수신자-home)에 따라 현재 응답 경계의 frame과 새 stream 또는 독립적으로 증명된 Codex 화면 응답에 묶여야 한다. 과거 status 뒤 새 startup/resume·다른 명령 또는 현재 신원 누락은 미확인이다. Claude의 부재 증명 경로는 agent가 명시 선택 pane에 연 status 모달을 마지막 설치 조회와 passive 대조까지 그대로 유지한다. 아래 중단 준비 검증의 조회 전용 모달 유지와 구분한다. 생성 또는 거부 결정 뒤 원래 runtime/self/설치/identity/상태 full guard와 정확한 원 모달 proof로만 Esc를 한 번 보낸다. changed/unverified UI에는 Esc 없이 `manual-status-modal-cleanup-required`를 기록하며, 정리 실패도 이후 대상 진행을 중단한다. 접수한 create는 정리 조회 전에 durable receipt를 보존하고, 불명확한 Esc나 create를 재전송하지 않는다. 일반 status/prepare는 계속 자체 모달을 닫으며 닫힌 frame을 이전 UUID에 연결하지 않는다. 선택 pane이 빈 shell이면 그 empty 화면/cursor도 마지막 조회를 가로질러 유지해야 한다. 새 동일 UUID 후보·unknown foreground·ps-only agent·workspace/self/상태 변화도 create 전에 중단한다. 이 최종 대조 뒤 새 설치 inventory·status·idle wait를 추가하지 않고 durable sending 기록 후 create한다. 이미 status를 접수한 실패는 기존 uncertain receipt를 보존한다. [native 대기·출력·진행·소유 정리 계약](runtime-refresh.md#수행-방법과-절차)을 재사용하며 durable batch에 새5분 만료를 두지 않는다. Orca list/ps와 compare/create는 비원자적이어서 마지막 passive 관측·로컬 기록·create 사이의 경합은 남는다.

소유 신규 terminal 또는 exact-resume 직후에는 기존10초 readiness deadline 안에서 `agent-identity-unknown`과 `child-state-unknown`만 입력 없이 재조회한다. target identity·설치·self·agent/child·busy·draft·approval guard 전체가 통과한 뒤에만 status와 후속 단계로 진행한다. 실제 child/working/trust/draft나 다른 오류는 재시도하지 않으며, unknown이 지속되면 중단한다. 일반 prepare/locate의 unknown 거부는 그대로다. 개별 CLI timeout 계약을 늘리거나 create/resume을 재전송하지 않는다.

Claude `/status`는 명령 전에 기존 `claude_permission` 문법으로 권한 표시가 확인돼야 한다. 표시만 없으면 최대3초/12회 안에서 full guard를 다시 읽으며 기다리고, 다른 guard 오류는 즉시 중단한다. 마지막으로 확인한 frame의 cursor/text를 새 응답 경계로 사용한다. 끝내 권한이 불명이면 `/status`를 보내지 않아 모달도 남기지 않는다. 저장 flags나 mode로 화면 권한을 추정하지 않으며 일반 prepare/native query에도 같은 거부를 적용한다.

### runtime 교체 뒤 현재 관리 helper 증명

원래 배치의 runtime이 바뀌고 현재 호출자의 pane이 선택 대상과 같은 workspace에 있을 때만, native 대화가 아닌 자기 관리 Python helper를 별도로 증명할 수 있다. 명시 예외와 원래 native self의 보호를 먼저 적용하며, UUID가 없는 예외의 이동 가능성을 이 증명으로 무시하지 않는다. 후보 terminal 목록의 순서와 무관하게 첫 native 조회 전에 현재 self를 유일하게 찾고, 완전한 local list/ps·새 show/screen에서 fingerprint·접근·연결·대기 없음·draft 없음을 확인한다. 전체 ps의 관측된 `paneKey` 또는 `parentPaneKey`가 self와 연결된 agent/child가 없어야 한다. provider hint가 null이거나 화면이 비어 있다는 사실만으로는 충분하지 않으며, 실행 중인 helper에 빈 shell prompt가 보일 필요는 없다.

독립 증거는 Linux `/proc/<pid>/stat`와 실행 파일 metadata다. 현재 Python3 실행 파일의 helper가 자기 process group의 leader이자 controlling TTY의 foreground group이어야 하고, 그 group에는 helper 하나만 있어야 한다. 직접 부모는 같은 계정·같은 TTY의 session leader인 system bash/zsh/dash 실행 파일이어야 한다. `/bin` 또는 `/usr/bin`의 해당 shell로 해석되는 root 소유·group/other 쓰기 불가 실행 파일만 지원하며 comm 표시로 shell을 판단하지 않는다. helper/부모 PID와 starttime·pgrp/sid/TTY/foreground 및 실행 파일 identity를 고정한다. stdin이 heredoc이어도 controlling TTY로 증명할 수 있지만, controlling TTY 없는 native agent tool subprocess·추가 foreground group 구성원·다른 부모·미지원 OS/shell·proc 권한 거부나 잘못된 자료는 보류한다. 스캔 중 사라진 다른 PID만 별도로 취급한다. 같은 TTY를 쓰는 별도 background group은 있을 수 있으며, foreground 소유 증명은 모든 background 작업 부재를 증명하지 않는다.

증거는 현재 client 메모리에만 runtime·self pane·fingerprint·process identity와 묶고 갱신해 새 권한으로 바꾸지 않는다. `execute` 진입마다 초기화하며 signed 배치·key·선택·예외·기존 event/실패 receipt나 출력 proof schema에 저장하지 않는다. 느린 조회 뒤 passive/shell guard와 create의 마지막 검증에서 이미 확보한 완전한 inventory를 재사용해 self metadata를 먼저 관측하고, target의 마지막 frame/proof를 확인한 뒤 runtime과 고정 `/proc` 증거를 다시 대조한다. status/exit/resume/raw modal key/create는 durable sending 기록 전과 직후에도 고정 process 증거를 비교한다. target의 최종 응답 proof 뒤에 새 Orca inventory/자기 화면 조회를 끼워 넣지 않는다. metadata·process·runtime의 불일치가 관측되면 다음 native 입력/create 전에 중단하며, sending 기록 뒤 불일치는 실제 전송 없이도 기존 uncertain receipt 정책을 유지한다. 마지막 self metadata 관측과 target 관측·로컬 기록·실제 입력 사이의 경합은 비원자 Orca API의 기존 한계로 남는다. 같은 runtime·다른 workspace와 일반 runtime-refresh는 이 예외를 새로 활성화하지 않는다.

### 명시 수동 예외 뒤 원래 미조회 tail 준비 계속

사용자가 첫 실패 대상을 수동 예외로 유지하고 나머지 준비를 계속하도록 명시 승인한 경우에만 `continue-prepare --batch <원 UUID> --exclude <첫 실패 handle>`를 실행한다. `--target`이나 새·복수 예외는 받지 않는다. 자동 재시도나 일반적인 실패 복구가 아니다. Claude auto mode의 권한 증명·resume 지원을 넓히지 않으며 그 대상에는 화면 관측·`/status`·모달 키도 보내지 않는다.

입장은 원 signed 배치의 `prepareState: complete`, 첫 restart 행의 native/attempt 없음과 `claude-permissions-unknown`, 나머지 원 restart 행의 `deferred/previous-target-failed` 및 미조회 상태에 한정한다. 전체 행에 native/attempt가 없어야 하며 이력은 해당 첫 행·handle·`prepare` operation의 같은 사유 `preparation-failed`와 뒤의 `prepared` 두 event만 정확히 있어야 한다. sending/accepted·모달·exit/create/resume·추가 event·다른 미해결 배치가 있으면 새 입력 없이 보류한다. 이력·key를 지우거나 새 배치로 대체하지 않는다.

같은 machine/profile·준비 runtime과 fresh local snapshot에서 모든 원 terminal fingerprint를 먼저 대조한다. 기존 manual/self는 metadata만 대조하며 입력하지 않는다. 원래 native self가 저장됐으면 현재 self와 일치해야 한다. 비에이전트 관리 shell의 원본에 self 행이 없으면 과거 self fingerprint를 추정하지 않고 현재 unique self 계약과 tail의 자기 입력 거부를 유지한다. 이 경우 과거 관리 shell과 현재 self가 같은 terminal인지는 원본으로 증명할 수 없다.

첫 실패 행만 `manual/explicit-exception`으로 바꾸고 원 실패 사유를 담은 `preparation-manual-exclusion` 결정 event와 `prepareState: started`를 먼저 durable 저장한다. 그 뒤 원래 미조회 tail만 원 순서대로 기존 `target_from/native_status`·설치/identity/권한/draft/working/approval/child/self 가드와 recorder로 준비한다. 첫 새 실패 뒤 tail은 그대로 중단한다. 원 batchId/binding/생성 시각/runtime/key·fingerprint·기존 선택·예외·실패/events를 보존하며 exit/resume/create는 실행하지 않는다.

이 명령의 Store는 기존 디렉터리·lock·key만 열고 없는 state/batch를 새로 만들지 않는다. 결정 저장 실패는 native 입력 전에 멈춘다. 결정 뒤 crash는 `started`로 남고 동일 continuation 재호출은 거부한다. 접수된 새 status 뒤 실패는 uncertain receipt를 보존하며 아래 status-only `verify`가 그 접수된 행만 복구할 수 있다. 이 명시 결정 event도 정확한 원 실패와 한 번의 결정으로 검증하며, verify가 미조회 tail을 발견·조회하도록 넓히지 않는다. 결정만 저장되고 status 접수 증거가 없으면 verify도 입력 없이 보류한다.

### 접수된 Claude 준비의 명시 복구

이전 ready/native Claude의 완료된 status/raw modal pair와 접수된 미완료 status가 함께 있거나, 접수된 조회 뒤 지원되는 status card가 열린 원 준비는 명시 `recover-prepare --batch <원 UUID>`로만 정리한다. 새 target/exclude·state/key/batch 생성·이력 편집·자동 재시도는 허용하지 않는다. 기존 status-only `verify`의 허용 범위를 넓히지 않는다. 원 machine/profile/runtime·terminal identity와 기존 선택·예외를 유지한다. 원래 접수된 선택 Claude 행만 원 순서로 조회하며 미조회 tail·manual/self는 입력하지 않는다.

입장은 `uncertain`, attempt 없음, 원 `prepare`의 짝이 맞는 status sending/accepted와 고유 requestId, 알려진 준비 실패/완료 event에 한정한다. raw one-byte pair는 바로 앞 status와 일치하고 이미 ready/native가 저장된 원 행의 완료된 modal 정리로만 인정한다. 이것으로 불명확한 과거 키를 Esc라고 추정하지 않는다. 미완료 navigation·extra/unknown/exit/resume/create 이력·유실/중복/불일치 receipt는 거부한다. 기존 첫 zero-input 실패의 단일 수동 결정은 원 계약대로 검증한다.

복구 시작을 먼저 durable 저장하고, 각 원 대상에서 fresh complete local list/ps·unique self·fingerprint·provider/설치·권한/draft/approval/working/child 가드를 확인한다. 현재 status card의 정확한 지원 header/footer와 고유 UUID/cwd/version·원 cwd 및 안정된 cursor/화면 SHA256을 확인한 경우에만 full guard와 같은 proof로 Esc를 한 번 보낸다. 닫힌 idle 화면을 확인한 뒤 새 `/status`로 identity를 얻는다. 정리 전 card UUID/cwd는 cleanup-only 연속성 대조값으로만 사용하며 새 status의 UUID/cwd와 다르면 native/attestation 채택 없이 중단한다. 정리 전 card는 fresh identity 증거가 아니며 권한·launch version의 근거로 사용하지 않는다. 원 native가 있으면 fresh UUID/cwd/권한도 모두 같아야 한다. 새 조회도 기존 native status의 단일 send·응답 경계·stable proof·정리 계약을 적용한다.

이미 저장된 `native`는 그대로 보존하고 별도 `resumeAttestation`과 `preparation-mode-attested` event에 fresh native mode/proof/operation을 저장한다. attestation은 원 UUID/cwd/권한·지원된 명시 mode·정확한 proof와 단일 event가 모두 맞아야 하며 execute/owned launch/재개 후 대조의 공통 `resume_basis`가 선택한다. 기존 null mode는 설치 버전이나 기본값으로 채우지 않는다. 관측 native319/329/330/331의 exact bypass만 인정하며 launch는 별도로 검증된330/331의 기존 고정 argv만 사용한다. 다른 version/auto/default/acceptEdits는 미지원이다.

첫 storage/transport/cleanup/status/proof/identity 실패에 남은 대상을 멈추고 원 이력과 새 durable 시도를 보존한다. 한 번 시작된 복구는 성공·중단·receipt 유실 뒤에도 다시 실행하지 않는다. fresh331의 관측된 두 placeholder `❯ Try "create a util logging.py that…"`와 `❯ Try "how does <filepath> work?"`만 정확한331 visible header와 기존 empty draft guard가 함께 통과할 때 조회를 허용한다. 소유331 관측에서 빈/restored frame은 draft 키를 생략했고, 각 hint와 같은 문자열을 직접 입력하면 별도 nonempty draft를 제공했다. 따라서 키 생략·null·빈 문자열은 기존 guard의 empty 값으로 처리하며, 실제 typed 동일 문구·다른 문구·다른 버전·header 부재는 거부한다. 이 source 지원의 native 완료 여부는 [검증 기록](../../../../../docs/verification.md)을 확인한다. exit/resume/create·사용자 세션 재시작·재부팅은 이 준비 복구에 포함되지 않는다.

### 접수된 조회만 있는 준비 검증

status-only 미완료 준비는 명시 `verify`로 검증한다. signed 배치의 모든 sending/accepted가 원 선택 restart 대상의 `status`이며 target/handle/operation이 순서대로 짝을 이루고 실제 requestId가 있어야 한다. 종료·재개·생성·모달 키 등 다른 단계나 attempt, 유실·불일치 receipt는 입력 없이 거부한다. 다른 미해결 배치도 기존처럼 차단한다. 같은 machine/profile·준비 당시 runtime·정확한 원 terminal fingerprint가 유지돼야 하며, 입력 전 fresh 설치/full guard를 다시 확인한다. 다른 runtime/handle을 locate로 추적하거나 inventory에서 UUID를 채우지 않는다.

원래 접수된 조회가 있지만 native identity가 비어 있는 행에만 새 `/status`를 한 번 보낸다. identity 저장 뒤 최종 준비 outcome 저장 전에 중단되어 비어 있는 queried 행이 하나도 없으면, 원래 queried 행만 다시 조회해 저장된 UUID/cwd/권한과 일치하는지도 확인한다. [Codex 대기·home 경로 계약](runtime-refresh.md#codex-status-응답-대기와-수신자-home)을 재사용하며 위 단일 계약의 stream/독립 Codex 화면 경계와 같은 원 frame proof를 확인한 뒤 UUID/cwd/권한과 응답 proof를 기록한다. 기존 실패/event를 보존하고 과거 row 사유도 덮기 전에 실패 event로 남긴다. 성공하면 그 행은 `ready`, 배치는 `prepareState: complete`와 별도 준비 검증 outcome이 된다. 미조회 tail·manual/self·기존 준비된 행은 그대로 남는다. 소비는 `unverified`, `consumedVersion: null`이다.

이 경로는 exit/resume/create·모달 탐색/닫기 없이 조회한다. 새 Claude status 모달이 생기면 원 proof와 함께 열린 채 유지될 수 있으며 이후 조작 전에 수동 정리가 필요하다. 현재 열린 모달 등 unsafe 상태는 입력 전에 보류한다. fresh 조회의 첫 실패도 기록하고 준비 미해결 상태를 유지하며 자동 재조회하지 않는다. 새 접수조차 유실됐으면 다음 verify도 차단한다. 새 배치나 다른 state 디렉터리, 기록·key 삭제/수정으로 우회하지 않는다.

## 명시 수동 예외의 신원 확인과 재검증

원 배치의 명시 `manual` Claude 예외가 선택 대화와 같은 workspace에 있을 때, 승인된 `identify-exception --batch <원 UUID> --target <원 targetId>`로 예외 신원을 한 번만 별도 확인한다. 사용자 UUID/PID/path 입력은 받지 않는다. 원 Store/key/서명/binding·선택·수동 state/reason·native 값(null 포함)·기존 events는 보존하고, 별도 `exceptionAttestation`과 정확히 대응하는 event를 추가한다. 없는/잘못된 Store·선택 대상·self·중복 확인은 native 조회 전에 거부한다. `list`의 `exceptionIdentity`는 이 별도 확인 metadata이며 `nativePrepared`를 대체하지 않는다.

현재 로컬 complete list/ps에서 원 pane/workspace/호스트의 유일한 Claude를 찾고, 기존 bounded `native_command`로 공식 Claude2.1.331 `agents --json`을 두 번 조회한다. query 실행체는 공식 native331이어야 하고, 대상 실행체는 관측된319/329/331 경로만 허용한다. producer의 검증된 절대 실행 파일을 version과 두 agents 조회의 `executable`로 고정해 전달하며, target cwd에서 bare `claude`나 상대 PATH를 다시 해석하지 않는다. 각 bounded 조회 전후와 최종 proof 경계에서 같은 파일 identity를 대조한다. 이 내부 선택 인자를 쓰지 않는 기존 runner 호출의 동작은 유지한다. Linux 같은 UID, 단일 PID namespace, 양수 PID/start tick, 실행 파일 identity, 실제 cwd와 `ORCA_PANE_KEY`를 두 조회 전후에 대조한다. names/status/JSON startedAt은 identity authority가 아니며 실제 시작 증명은 proc start tick이다. 같은 cwd의 관련 process가 읽히지 않거나 background를 포함해 같은 pane·PID·UUID가 모호하면 중단한다. private registry·transcript·argv를 읽지 않고 환경 원문은 저장·출력하지 않는다.

후속 선택 `verify/restore/restart`는 과거 attestation에서 UUID/원 pane/workspace만 기대값으로 읽고 현재 공식 API/process로 새 증명을 만든다. 새 boot/PID/start/namespace는 같은 UUID·원 pane/workspace가 새로 입증될 때만 허용하며 과거 attestation은 고치지 않는다. 이 invocation에서 얻은 live 또는 absent 판정과 runtime/terminal/API 기대값은 이후 wait·설치 조회 동안 고정하고 재기준화하지 않는다. live이면 같은 process 증명도 고정한다. manual의 terminal 화면은 조회하지 않으며, manual/self에는 입력·종료·launch를 수행하지 않는다. 기존 관리 helper의 self 화면 관측은 유지한다. 알려진 예외 pane만 선택 후보에서 제외하고, 부재 증명의 ps 허용 집합에도 방금 입증한 pane만 더한다. ps-only agent, unknown exception, 새 UUID/pane, 다른 producer, 선택/native 충돌과 중복은 계속 거부한다.

선택과 확인된 manual이 모두 꺼진 재부팅 흐름도 지원한다. 원 manual pane가 complete local terminal 목록 어디에도 없고, ps에도 원 pane·parent/child/subagent 연관이 없으며, 원 workspace의 ps-only/unknown agent가 없을 때만 `known absent` 후보가 된다. 이어 두 공식 active JSON 전체에서 expected manual UUID가 없음을 확인하고, 다른 cwd를 포함한 공식 active interactive/background process 전체를 bounded 지원 proc 증명으로 전후 대조하여 원 pane 재사용이 없음을 확인한다. 다른 pane/cwd에서 expected UUID가 살아 있거나, 원 pane에 nonagent/unknown terminal이 남았거나, active process의 proc/목록을 읽지 못하면 부재로 전환하지 않는다. live 신원 확인의 다른 cwd process 무조회 범위는 유지한다. 이 부재 증명은 저장된 live attestation을 바꾸지 않고 invocation 메모리에만 둔다. 부재인 예외 pane는 ps 허용 집합에 넣지 않는다.

부재 proof의 고정 대상은 expected UUID·원 pane/workspace·producer/query 실행체와 absent 판정이다. active process 전체는 각 두 공식 조회 전후에 검증하지만 그 목록을 manual 부재 identity로 삼지 않는다. 정상적으로 create한 선택 process가 나타나도 같은 manual 부재를 다시 확인할 수 있으며, manual의 live/absent 전환이나 UUID/pane 재사용은 같은 invocation에서 새 authority로 채택하지 않는다. 매 full guard는 공식 부재와 fresh Orca 부재를 다시 확인한다.

긴 lookup 뒤 새 공식 JSON으로 같은 UUID/live proof 또는 같은 known-absent proof를 재확인하고, 그 뒤 fresh list/ps와 최종 선택 frame/modal·management proof를 대조한다. 예외가 있는 create는 durable sending을 이 최종 공식 조회 앞으로 기록해, 저장 중 바뀐 같은 PID의 UUID나 부재 상태도 create 전에 거부한다. 마지막 선택 frame 뒤에는 고정 로컬 실행체와 live process 증명만 읽으며 새 설치/native 조회·wait를 넣지 않는다. 실패 후 receipt를 보존하고 재조회로 새 authority를 만들거나 create를 재시도하지 않는다. 마지막 공식 관측과 frame·create 사이의 비원자 경합은 남는다. 실제 PC reboot와 운영 배포는 이 source 구현의 검증 범위가 아니다.

## 연계와 의존

| 대상 | 입력과 필요한 결과 | 부재·오류 처리 |
|---|---|---|
| Orca CLI | 기존 실행 파일 선택 계약, local list/ps/show/read/wait/send/create. 완전한 local scope, 새 handle/receipt와 현재 workspace identity | 필수. 현재 버전의 공식 orca-cli guide/해당 command help에서 계약을 확인한다. unknown receipt나 미지원은 중단하며 임의 RPC/DB/daemon으로 대체하지 않는다 |
| 제품 native CLI의 기존 공식 관리자 | 업데이트가 승인된 대상·버전/채널·설치 방식·기존 계정, 사전 batchId/UUID/예외를 전달한다. 현재 설치 방식의 공식 업데이트 문서와 지원 명령을 확인해 실행 파일·버전·관리자 결과 및 소유 resume canary의 identity/권한 결과를 받는다 | 해당 승인 범위에만 필수. npm 등 실제 사용 중인 공식 package manager 또는 native updater를 재사용하며 미확인 설치 방식·계정·채널을 추측해 전환하지 않는다. 관리자 실패·권한 거부·canary 미통과는 해당 호스트와 이후 적용을 보류하며 무승인 자동 업데이트·권한 변경으로 대체하지 않는다 |
| `runtime_refresh.py` | passive eligibility, 설치 inventory, 입력 전 guard, native status의 제한 mode와 고정 resume 구성, 정상 Codex 종료와 접수 기록 | 같은 디렉터리의 단일 구성기를 refresh/restart/restore가 재사용한다. 미확인 권한 보존은 수동, 실패는 해당 대상과 이후 대상을 중단. private 의존 없음 |

## 제약과 주의점

PC 재부팅·강제 종료·기존 대화 fork/대체·`--last`·저장된 command 재생·권한/trust 변경·자동 시작 등록·예외를 무시하는 bulk restore를 하지 않는다. 테스트는 소유 canary만 사용한다. 현재 source/fake 통과는 실제 terminal 생성·Claude 종료·제품별 UUID 보존의 native canary를 대신하지 않는다. 배포 전에 별도 canary에서 이 계약을 확인해야 한다.

## 결과와 완료 판단

대상별 `restarted`, `already-running`, `manual-restart-required`, `deferred`, `failed`와 사유를 구분한다. 첫 실패 뒤 남은 대상은 `deferred/previous-target-failed`다. 요청자의 native 세션은 수동 목록에 명시한다. 설치 inventory는 준비/실행 시점에 따로 확인하며 업데이트 뒤 새 설치를 허용하되 한 조작 중 drift는 중단한다. 새 프로세스의 UUID/cwd/권한 확인, 입력 접수와 플러그인 소비는 별개다. `consumption: unverified`, `consumedVersion: null`을 유지하며 실제 소비 완료로 보고하지 않는다.

## 실패와 복구

기본 저장 위치는 `~/.local/state/tr-kit/session-restart`, 선택 override는 `--state <호스트 로컬 경로>`다. 배치·진행 기록·integrity key는 Git/동기화/배포물에 넣지 않는다. 대화·화면·프롬프트·native 출력 원문과 실행 command를 저장하지 않는다. 디렉터리 0700, 파일 0600, symlink/hardlink 거부, descriptor 고정, atomic replace/fsync와 host-local lock을 사용한다. signature는 우발 수정 검출이며 같은 계정 소유자의 악의적 변경 방지는 아니다.

모든 입력/launch 전에 metadata 기록을 fsync하고 이후 실제 receipt를 기록한다. timeout·crash·저장 실패는 같은 command 재전송이나 새 terminal 생성으로 복구하지 않는다. `list`와 현재 read-only 상태로 마지막 시도/정상 종료/소유 terminal 증거를 대조하고, 후속 명시 `verify` 요청에서 검증한다. 미해결 배치가 있으면 다른 배치 실행도 보류한다. 준비 중 불명확한 접수는 `prepareState: uncertain`으로 보존하며 자동 재준비하지 않는다. 재개 중 update 메뉴나 권한 drift도 성공이 아니다. 기존 실패와 같은 배치를 보존한다. 승인된 같은 모드 보존과 권한 증가·임의 flags 재생을 구분하고, 신뢰/전역 설정을 바꿔 통과시키거나 새 배치의 성공으로 덮지 않는다. 별도 기본 launch 조건의 소유 canary는 원래 실패와 구분해 기록한다. 과거 header scroll-out 보류 기록은 유지한다. 후속 관측에 따라 header가 전혀 없고 정확한 기본 placeholder·빈 draft인 frame은 조회/status까지 허용하되, 보이는 미지원 version header와 typed draft는 계속 거부한다. 화면 header 부재를 버전 지원 근거로 삼지 않고 fresh status의 nativeVersion·현재 CLI 버전이 미확인이면 exit/create 전에 수동 처리한다. 소유 canary에서 수행한 수동 status 보정은 자동 prepare의 단독 성공 증거가 아니다. 기록·key·잠금 파일을 지워 우회하지 않는다. CLI는 원자적 idle-종료/부재-launch 계약이 없으므로 직전 재확인 사이의 외부 조작 경합까지 제거하지는 못한다.
