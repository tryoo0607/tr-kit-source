# 실행 중 세션의 runtime 갱신

열린 Codex와 Claude의 플러그인 반영 상태, 보류 목록과 설치 후 갱신 요청에 사용한다. 기본은 조회다. 설치 버전, 갱신 입력 접수와 실제 소비 증거를 구분한다.

## 입력과 전제

대상 호스트, 설치 결과와 명시 선택한 terminal handle 및 승인 범위를 받는다. 기존 설치 근거를 재사용하고 새 설치가 필요한 경우에만 아래 native 설치 연결을 적용한다. 갱신 승인은 설치, 배포, 전체 daemon 재시작이나 다른 세션 종료 승인이 아니다.

`ORCA_PANE_KEY`와 조회 결과의 `tabId:leafId`로 실행 주체를 식별한다. cwd나 대화 ID만으로 self를 추정하지 않는다. self를 유일하게 찾지 못하면 전체 적용을 보류한다. structured chat은 terminal 수단으로 갱신하지 않는다.

## 수행 방법과 절차

1. 현재 skill 디렉터리의 `scripts/runtime_refresh.py`를 Python 3으로 실행한다. 인자 없이 또는 `inspect`로 조회한다. Orca의 기존 실행 파일 선택 계약으로 CLI를 한 번 정해 list, ps, show와 screen read를 사용하며 사용자 창에 입력하지 않는다. 출력은 host 범위, handle, incarnation, cwd, 상태, 보류 사유와 native 설치 버전 metadata를 포함한다. 로컬 `codex plugin list --json` 또는 `claude plugin list --json`을 해당 cwd에서 조회하며 native CLI 버전, 플러그인 ID, 설치 버전, 활성 상태와 scope를 정리한다. CLI의 source, 경로, 진단 원문과 비밀 필드는 출력하지 않는다. 이 inventory는 호출자의 config 환경 기준이며 대상 runtime의 실제 소비 증거가 아니다. 원격 설치 inventory는 해당 호스트 수신자에게 위임한다. 누락 호스트와 truncated 결과를 전체 기기 조회로 해석하지 않는다.
2. 설치 inventory가 확인된 명시 선택 idle만 `plan --target <handle> [--target <handle>] --plan <새 JSON 경로>`로 저장한다. self, busy, 초안, 승인 대기, 자식 작업과 상태 또는 identity 불명은 제외한다. 빈 idle prompt와 agent·main 상태 및 program 완료 근거를 확인해야 한다. Codex는 program 객체의 done/idle을 계속 요구한다. Claude의 programStatus가 null 또는 부재이면 aggregate와 main이 모두 done이고 실제 `tui-idle` receipt가 만족하며 identity와 자식 상태 근거가 함께 확인될 때만 허용한다. null 자체를 idle로 간주하지 않는다. UI의 `draft`와 native prompt의 입력 문자열은 초안으로 보류한다. Codex0.167.1의 header와 정확한 기본 placeholder는 소유 canary에서 대조한 범위만 허용하고 그 외 형식은 보류한다. native Codex와 Claude의 빈 roster 생략은 aggregate와 main이 done이고 program이 done 또는 idle일 때 허용하며, Claude의 null/부재는 앞의 엄격한 완료 조건을 함께 충족해야 한다. 명시된 자식 목록이나 미확인 관측은 보류한다.
3. 승인된 대상에만 5분 이내 `apply --plan <JSON 경로>`를 실행한다. 원격 조회는 `--environment <selector>`를 사용하되 원격 apply는 아래 session 연결로 해당 호스트 수신자에게 위임한다. 수신자는 그 호스트의 기존 가드를 적용하고 자신을 제외해 새로 조회 및 계획한다. 송신자의 self 정보를 원격 self로 대체하지 않는다.
4. 입력마다 계획에 저장한 설치 inventory와 현재 버전 및 활성 상태를 대조하고 runtime, handle, PTY, incarnation, pane, cwd, host와 현재 상태를 재조회한다. 설치 정보가 바뀌거나 조회할 수 없으면 입력 없이 중단한다. 실행 후에도 설치 inventory를 대조해 drift를 별도로 판정한다. Codex에서는 `/status`의 새 출력에서 exact UUID, cwd와 권한을 얻은 뒤 `/exit`로 정상 종료한다. /exit 직전 stream cursor 이후 새 정상 종료 안내에 같은 UUID가 있고 현재 마지막 frame이 빈 shell prompt이며 agentWait와 집계 live child가 없을 때만 shell 복귀를 인정한다. terminal show의 agentIdentity는 종료 후에도 남을 수 있으므로 그 hint 하나를 foreground 생존 근거로 삼지 않는다. 종료 안내 원문은 출력하거나 저장하지 않고 확인된 UUID와 shell cwd만 journal에 남긴다. 이 증거가 갖춰졌을 때만 같은 터미널에서 `codex resume <exact UUID>`를 실행한다. `--last`, 새 대화 대체나 새 권한 우회 flag를 쓰지 않는다. 다시 `/status`를 조회해 UUID, cwd와 권한을 대조한다. shell, 메뉴, 신뢰 확인이나 권한이 불명확하면 추가 입력 없이 멈춘다.
5. Claude는 설치본의 `/reload-plugins` 지원, 누락 의존성 설치가 필요 없다는 근거와 완료 응답을 확인했을 때만 native reload를 사용한다. `--force`를 쓰지 않는다. script는 native CLI2.1.260 이상의2.1 계열, 활성 플러그인의 manifest와 의존성 설치 상태, 진단 부재를 확인한다. manifest를 읽지 못해도 조회된 설치 버전은 보존하고 reload는 보류한다. 의존성은 설치되고 활성인 유일한 ID 및 필요한 exact 버전만 허용하며 미지원 버전 범위는 보류한다. 대상 `/status`의 CLI 버전과 identity, 새 `/help`의 명령 지원, 새 `/plugin list --enabled`와 설치 목록의 일치를 확인한 뒤에만 `/reload-plugins`를 보낸다. 새 출력의 완료 요약과 플러그인 수를 확인하고 identity 및 설치 상태를 다시 대조한다. Claude2.1.322에서 관측한 status/help 모달 형식을 지원한다. 새 status 모달과 직전 idle 화면의 명시 권한 근거를 확인하고 Esc로 닫으며, help는 알려진 모달 안에서 Right와 최대 16회의 Down 10개 단위 탐색으로 Commands 목록을 확인한 뒤 닫는다. 각 입력 전후 identity·대기·모달 경계를 재확인하고 미확인 화면은 중단한다. 모달 raw key는 `--enter` 없이 보내며 실제 receipt의 handle 일치, accepted=true와 입력 UTF-8 길이에 정확히 맞는 bytesWritten을 검증한다. raw receipt에는 mutation이나 prompt가 없을 수 있고 request ID를 만들어 넣지 않는다. 제공된 mutation의 requestId와 prompt의 incarnation은 검증하고 실제 접수 metadata만 journal에 기록한다. 반면 `--enter` 명령 제출은 기존 mutation.requestId를 계속 요구한다. 어느 영수증이든 불명확하면 재전송하지 않는다. stream에 UI가 없으면 새 모달 또는 새 명령 echo 뒤의 비어 있지 않은 응답 경계를 확인한다. echo 수 증가로 새 경계가 독립적으로 입증된 경우 이전과 같은 본문도 허용하지만 과거 화면이나 echo만으로 완료를 판정하지 않는다. 이 구현과 회귀 검사는 변경된 script의 실제 native 갱신 완료를 의미하지 않는다. force 요구, 오류, 의존성 추가 설치 응답과 모호한 출력은 부분 변경으로 중단한다. 확인된 수단이 없는 버전을 지원하는 것으로 보고하지 않는다.
6. 한 대상의 identity 대조와 증거 정리 후에만 다음 대상으로 진행한다. 설치된 버전과 실제 소비 버전은 별도 근거로 대조한다. script는 native resume 확인만으로 플러그인 소비 완료를 판정하지 않으며 `consumption: unverified`를 반환한다.

## 연계와 의존

| 대상과 요청 | 입력 | 필요한 결과 | 의존과 부재 시 동작 |
|---|---|---|---|
| 제품 native 설치 CLI: 설치 상태 확인과 필요한 설치 작업 | 제품, 플러그인과 버전, 기존 설치 근거, 승인 범위 | 설치 버전, 확인 결과와 runtime 반영 미결 | 기존 근거 재사용. 실제 지원 명령을 확인할 수 없으면 설치와 후속 반영 보류 |
| Orca CLI: 읽기 전용 조회와 선택 대상의 순차 입력 | host 범위, runtime handle, 실행 주체 pane, 승인된 대상 | runtime 및 incarnation, agent와 program 상태, native 완료 증거와 접수 request ID | 필수. JSON 실패, 누락 상태, timeout과 불명확한 접수는 중단. 임의 RPC나 자체 세션 관리기로 대체하지 않음 |
| session: 원격 호스트의 기존 수신자에게 갱신 위임 | 호스트, 수신자, 설치 근거, 승인 범위와 선택 대상 | 해당 호스트의 가드 적용 결과, 보류 사유와 복구 좌표 | 원격 적용에 필수. [session 본문](../SKILL.md)의 위임 분기로 진입. 수신자 또는 권한 불명은 실행 보류 |

이 배포본에 별도 kit skill이 있다고 가정하지 않는다. script는 반복 조회, 제외, 순차 조작과 metadata 정리를 맡고 native 설치나 제품 동작을 대체하지 않는다.

## 제약과 주의점

다른 세션 원문 검색, 강제 종료, process 이름 전체 종료, 전체 daemon 재시작, 캐시 변경과 임의 배포를 하지 않는다. screen은 상태와 native metadata 판별에만 사용하며 prompt, preview, 대화 문장과 비밀 필드를 출력하거나 저장하지 않는다. 기존 사용자 창을 회귀 시험 대상으로 입력하거나 종료하지 않는다. 실제 시험은 새로 만든 소유 canary만 사용한다.

Orca에는 원자적 idle 확인과 종료 계약이 없다. 직전 재확인은 경합을 줄이지만 완전한 무경합을 보장하지 않는다. 두 제품의 aggregate는 추적 중인 자식 상태를 반영하지만 미추적 백그라운드 작업의 부재까지 입증하지 않는다. live Orca1.4.242/Codex0.167.1의 소유 A/B 시험에서 native text-only 입력도 `draft`로 분리되는 것을 관측했다. 기본 placeholder와 같은 문자열을 입력한 경우도 해당 필드로 차단한다. 다른 버전, 직접 키보드 입력과 화면 폭의 모든 조합까지 입증한 것은 아니다. 조회 후 상태나 대상이 바뀌면 중단한다.

## 결과와 완료 판단

호스트 조회 범위, self와 제외 사유, 명시 선택, 대상별 before/after UUID, cwd와 권한, 설치 버전 근거, 갱신 접수 및 실제 소비 근거, 남은 대상과 보류 사유를 전달한다. 설치 버전이나 PID, PTY 변경, native resume 성공만 확인되면 적용 미확인이다. 설치 버전은 `installedVersion`과 `installationBefore/After`, 실제 소비 버전은 `consumedVersion`으로 분리한다. 현재 API는 제품별 플러그인의 실제 소비 버전을 입증하지 않으므로 `consumedVersion: null`, `consumption: unverified`를 유지한다. native reload의 완료 요약도 버전별 소비 증명으로 확장하지 않는다. 완료는 승인 대상에서 identity 보존과 새 skill 및 hook 소비를 각각 관찰했을 때만 판정한다.

## 실패와 복구

첫 실패 뒤 나머지는 중단하고 `remaining`, 실패 대상 identity와 journal 경로를 반환한다. 미해결 operation이 남아 있으면 다른 operation도 보류한다. journal은 기본 `~/.local/state/tr-kit/runtime-refresh`에 metadata와 실제 접수 request ID 또는 raw key receipt의 handle·accepted·bytesWritten을 저장한다. `--journal <경로>`로 호스트 로컬 위치를 지정할 수 있다. 원문이나 pairing secret을 넣지 않는다.

입력 전에 operation을 기록하고 호스트별 lock을 잡는다. 같은 operation의 재실행과 동시 apply는 거부한다. journal은 부모부터 symlink를 따라가지 않고 directory descriptor에 고정하며 record를 exclusive 생성한다. record 교체나 hardlink를 감지하면 쓰기와 후속 입력을 중단한다. symlink 경로, 그룹이나 다른 사용자에게 쓰기가 열린 journal 디렉터리와 해당 가드 미지원 호스트는 보류한다. timeout이나 crash 뒤 새 operation으로 재전송하지 않는다. journal의 마지막 단계, runtime 및 incarnation, native UUID와 현재 화면을 먼저 대조한다. 확인된 Orca request ID가 있으면 같은 request의 접수 상태만 조회하고 새 입력으로 대체하지 않는다. script는 자동 재전송하지 않는다.

정상 종료 후 resume 실패, identity나 권한 불일치, 메뉴와 승인 대기는 부분 변경이다. UUID와 cwd 및 권한 근거를 보존해 해당 수신자의 승인된 native 복구로 이어간다. 오래된 lock이나 journal을 지워 맹목 재실행하지 않으며 상태를 먼저 확인한다. 실패를 추가 설치나 대상 밖 세션 종료로 덮지 않는다.

설치 JSON과 reload 요약의 제품 계약은 [Claude 공식 명령 문서](https://code.claude.com/docs/en/plugins/cli-reference), 의존성 형식은 [manifest reference](https://code.claude.com/docs/en/plugins-reference#dependencies)를 근거로 한다. 현 호스트의 실제 CLI 지원과 출력이 다르면 실행을 보류한다.
