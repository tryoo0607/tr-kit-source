# 같은 cursor의 Codex status 화면 응답 증명

R-52의 승인 계획은 `_bmad-output/plan-codex-status-screen-proof.md`이며 baseline은 `666b82dee2aa65f73b33d4bc2517c29c8d917afe`다. 기존 stream 필수 조건 중 독립적으로 증명된 Codex `/status` 화면 응답만 보완한다. 구현자의 범위는 지정 worktree의 source·회귀·계약·기록이며 원격 작업·commit/push·package·활성화는 포함하지 않는다.

## 근거와 결정

계획에는 Orca1.4.242/NAS Codex0.167.2가 새 status 카드를 화면에 추가했지만 완료 newline cursor는6이고 fresh stream이 비었다는 관측이 있다. 지정된 `codex-status-screens.json`은 실제 내용·계정·대화가 제거된 줄 순서/동등성 합성 자료이며 native 증거가 아니다. 구현자는 해당 원격 화면을 직접 조회하거나 입력하지 않았다. 추가로 root는 현재 화면이29행, marker1개이고 `truncated=true`이며 `--limit1000`에도 같다고 전달했다. 이 전달 관측 역시 구현자의 native 실행 성공으로 취급하지 않는다.

기존 `native_query`의 단일 send·bounded passive guard와 `finish_response`/`output_proof`를 재사용한다. `codex_screen_status`는 입력 전후 이력의 순서와 이전 응답 끝을 보존하는 overlap으로 새 marker/card를 증명한다. 전체 이력 보존과, 이전 Session 줄을 포함한 유일한 suffix 앞에 기존 첫 사용자 prompt가 남는 합성 관측 형식을 지원한다. 새 카드의 필드와 가용 stream 신원을 `codex_screen_identity`가 엄격히 대조한다. 조건·상한·지원 형식·거부의 단일 정본은 [runtime-refresh](../../common/base/skills/session/references/runtime-refresh.md#codex-status-응답-대기와-수신자-home)에 둔다.

`output_proof`는 기존 cursor/screenSha256 사전을 유지한다. 추가 metadata event를 만들지 않고 기존 `awaiting-native-response`를 사용하므로 `session_restart.py`의 status-only allowlist와 정확한 proof 비교 소비자를 바꾸지 않는다. prepare/verify/restore의 호출부와 signed Store·failure/history·예외·소비 상태는 재사용한다. batch 복구에는 [기존 공통 계약](../../common/base/skills/session/references/session-restart.md#접수된-조회만-있는-준비-검증)을 연결한다. 파일 배치·외부 의존·설치 방식·권한·계정·private 연결은 변경하지 않는다.

## 검증과 한계

[검증 기록](../verification.md#codex-status-화면-응답-증명--2026-11-23)에 source/fake/native 층위와 실행 로그를 구분한다. 동일 화면·footer만 바뀐 반복·이전 suffix가 중복된 cropped 반복은 새 응답을 입증하지 못하므로 계속 보류한다. 이미 두 번 status를 받은 현재 NAS도 이 제한에 걸릴 수 있으며, 추가 status·다른 명령·UI 조작으로 해소하는 구현은 없다. 이력 노출·resize/reflow로 순서가 불명확하거나 지원 header/marker 형식이 다르면 성공으로 보고하지 않는다.

실제 native NAS 검증·독립 quick 검수·전체 CI/실제 Gitleaks8.30.1·새 pin/package·rollout은 root의 후속 범위다. source/fake 통과가 native 복구·재시작·플러그인 소비를 증명하지 않는다. 원자적 compare-and-send가 없으므로 마지막 관측 뒤 외부 조작 경합도 남는다.
