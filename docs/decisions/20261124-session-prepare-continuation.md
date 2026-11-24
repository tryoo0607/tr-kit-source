# 명시 수동 예외 후 같은 배치의 미조회 준비 계속

## 요구와 결정

R-52의 inno-desktop 준비에서 첫 Claude auto mode의 권한 증명이 미지원이어서 native 입력 전에 중단됐고, 원 배치는 실패 행과 미조회 tail을 보존했다. 사용자 승인 “권장안으로 보완·검증 후 계속”(2026-11-24)과 `plan-session-prepare-continuation.md`에 따라 그 첫 대상을 수동 예외로 유지한 뒤 같은 signed 배치의 원 미조회 대상만 준비한다. 원본 계획의 baseline은 `1e53a5100012089f5075e671bca758886deec23d`다. 구현자의 독립 native 관측이 아니라 root가 전달한 기존 운영 실패이며 source/fake 시험과 분리한다.

## 변경과 보존

기존 `session_restart.py`의 `continue-prepare`가 정확한 zero-input 실패 event pair·원 handle·단일 명시 제외·same binding/runtime·모든 원 fingerprint를 검증한다. manual 결정 event와 started 상태를 먼저 저장하고 기존 prepare의 순차 row 준비/full guard/recorder/signed Store를 재사용한다. existing-only 입장은 state·lock·key나 대체 batch를 만들지 않는다. 이전 batch identity·key·terminal identity·수동/self 선택·실패/events는 보존하고 첫 실패 행의 선택만 명시 manual로 바꾼다. 상세 조건은 [운영 계약](../../common/base/skills/session/references/session-restart.md#명시-수동-예외-뒤-원래-미조회-tail-준비-계속)에 한 번만 둔다.

반복 continuation은 거부하며 기존 status-only verify는 정확한 단일 결정 event와 새 acknowledged status만 인정한다. 미조회 tail을 새로 찾거나 exit/resume/create하지 않는다. auto mode 지원·권한 옵션·설치/원문·배포 경로를 바꾸지 않는다. source 배치와 외부 공급자는 기존 연결을 재사용한다. 실제 원격 적용·버전 변경·패키징·Git publication은 구현자의 범위 밖이다.

## 검증과 한계

실제 tempfile signed Store·소유 transport doubles에서 원 key/event prefix/row identity 보존과 원 tail의 정확한 입력 순서, unsafe/binding/runtime/fingerprint/receipt/attempt·스토리지 실패·재호출·CLI no-create 입장·acknowledged-tail 한정 verify를 검사한다. suite 및 독립 검수·후속 전체 CI 결과는 [검증 기록](../verification.md#명시-수동-예외-후-미조회-준비-계속--2026-11-24)을 따른다.

기존 실제 배치는 비에이전트 관리 shell이라 과거 self 행이 없다. 그 fingerprint를 복원하거나 추정하지 않으며 현재 unique self 및 tail self 거부만 증명한다. 원본에 없는 과거와 현재 관리 terminal의 동일성은 미확인이다. source/fake 성공은 receiver-local native continuation·native identity/권한·restart·플러그인 소비·실제 압축/재개 성공이 아니다. 마지막 passive guard와 native 입력 사이의 기존 비원자 경합은 남는다.
