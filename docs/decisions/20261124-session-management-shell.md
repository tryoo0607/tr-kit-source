# Runtime 교체 뒤 자기 관리 helper 구분

## 요구와 결정

재시작 배치 R-52의 기존 자기 세션·명시 예외 보호는 유지한다. 사용자 승인 “관리 shell 구분 보완·검증 후 계속”(2026-11-24)에 따라, runtime이 바뀐 뒤 대상과 같은 workspace에 있는 현재 비에이전트 관리 helper만 별도 증명한다. null provider hint·빈 draft·화면 hash는 단독 허용 근거가 아니다.

## 변경과 책임

기존 session_restart.locate가 명시 예외 보호를 먼저 적용하고 후보 조회 전에 자기 helper 증명을 확정한다. 공통 runtime_refresh의 process/metadata 증명이 고정 evidence를 client 메모리에서 비교하며 passive/shell guard와 status/exit/resume/raw-modal/create 경계에서 재확인한다. 기존 두 helper와 session-restart reference 안의 보완이며 새 skill·hook·provider·설치 방식은 추가하지 않는다. 파일 배치와 실제 호출은 [구조](../architecture.md#자기-관리-helper-구분--2026-11-24), 상세 지원·거부 조건은 [실행 계약](../../common/base/skills/session/references/session-restart.md#runtime-교체-뒤-현재-관리-helper-증명)을 따른다.

원 signed 배치·key·UUID·선택·예외·이전 failure/events는 보존한다. 증명은 저장된 command나 권한 flag가 아니며 batch/output-proof schema를 바꾸지 않는다. 새 배치·다른 state·기록 삭제·설치본 직접 수정으로 기존 보류를 우회하지 않는다.

## 검증과 한계

합성 transport의 동일 배치·self 무입력·예외 우선·증거 drift와 실제 소유 PTY의 foreground/heredoc/group 충돌을 구분한다. 독립 quick 정적 검토의 발견 사항은 없었다. 최종 suite와 패키지/native 적용 결과는 [검증 기록](../verification.md#자기-관리-helper-구분--2026-11-24)을 따른다.

증명은 지원 Linux process/TTY·system shell 실행체와 현재 Orca self 계약에 한정한다. 모든 background 작업의 부재나 불변 상태를 인증하지 않는다. 최종 own metadata 관측 뒤 target 관측·로컬 기록·실제 입력 사이의 비원자 경합이 남으며, sending 기록 뒤 증거가 바뀐 경우 실제 전송 없이도 기존 uncertain 복구 원칙을 유지한다. source/fake·소유 PTY 통과를 사용자 native 세션 재시작이나 실제 플러그인 소비 성공으로 확대하지 않는다.
