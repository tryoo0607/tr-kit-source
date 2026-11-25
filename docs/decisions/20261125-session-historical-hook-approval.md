# 완료된 과거 Hook 오류와 현재 승인창 구분

## 요구와 결정

승인 계획 `plan-session-historical-hook-approval.md`(2026-11-25)와 사용자 `과거 오류와 실제 승인창을 구분하도록 보완·검증 후 계속` 승인은 원래 NAS 배치가 입력 전에 중단된 분류 오류만 대상으로 한다. 직접 관측한 로컬 화면에는 정확한 Hook 실패 두 줄과 바로 다음 완료 시간 표시, 지원된 빈 composer가 있었다. 개인 metadata·계정·UUID·cwd·대화와 화면 원문은 저장소에 복사하지 않는다. 과거 오류를 분류에서 제외해도 그 Hook 실패가 해결됐다는 뜻은 아니다.

기존 공통 `idle_screen`의 dialog 단어 검사에서만 단일 완료 오류의 메시지 한 줄을 제외한다. 원본 text/frame·status proof는 변경하지 않고 shared runtime을 사용하는 restart 경로를 그대로 재사용한다. 상세 지원·거부 조건은 [단일 runtime 계약](../../common/base/skills/session/references/runtime-refresh.md#완료된-과거-hook-오류와-현재-승인창)에 둔다. 새 skill·hook·config·private 복사본이나 native 입력 복구는 없다. source77의 inline/readiness/zsh와 Claude 동작, identity·child·권한·freshness·receipt·단일 입력 가드는 보존한다.

## 검증과 한계

합성 fixture는 정확한 완료 묶음, 다른 현재 승인·선택·확인 문구, 누락·변형·미완성·순서 변경·중복, draft·header·prompt·제어 문자, 기존 상태 가드와 status 원문/proof 보존·freshness를 검사한다. fixture의 시간·요청·footer는 합성 값이다. 시험 명령·실제 수·실패 및 미실행 범위는 [검증 기록](../verification.md#완료된-과거-hook-오류-분류--2026-11-25)을 따른다.

이 변경은 모든 과거 오류나 마지막 prompt 앞의 전체 text를 면제하지 않는다. 새 formatter나 중복 완료 경계는 보수적으로 미지원이며 표시를 숨기거나 trust/config/권한을 바꿔 통과시키지 않는다. 로컬 source 시험은 실제 NAS 원래 배치의 재시작·현재 Hook 성공이나 설치·plugin 소비 근거가 아니다. 원래 배치의 not-submitted·exit0/resume0과 이전 실패·키·이력은 parent 소유 후속 검증 전까지 그대로다. parent가 독립 quick 검수, 전체 공통 CI, 실제 소유/반복/원래 NAS 검증과 package/private pin·승인 delivery를 별도로 수행한다.
