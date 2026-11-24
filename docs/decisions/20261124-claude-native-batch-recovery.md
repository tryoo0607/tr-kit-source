# 접수된 Claude 준비의 같은 배치 복구와 legacy 권한 보존

## 입력과 전제

승인 계획 `plan-claude-native-batch-recovery.md`의 baseline `d7128e3b095dd341e4ca57c45e3e0d9b2fc5f090`에서 구현했다. 이전 ready Claude319의 status/완료된 raw modal pair와 접수된 미완료 Claude329 status를 같은 signed 배치에서 복구한다. 원 native 기록·key·선택·예외·실패·event prefix를 보존한다. 원 호스트 대화·설치 파일은 이 구현 과정에서 조작하지 않았다.

## 수행 방법과 절차

운영 계약은 [session-restart](../../common/base/skills/session/references/session-restart.md#접수된-claude-준비의-명시-복구)가 소유한다. `recover-prepare`는 기존 state/key/batch만 열고 원래 접수된 선택 Claude 행만 대상으로 삼는다. 기존 status-only `verify`는 modal 이력을 계속 거부한다. 한 번의 복구 시작을 입력 전에 저장하며 중단 뒤 재호출은 허용하지 않는다. 현재 card의 고유 UUID/cwd/version과 정확한 header/footer는 cleanup의 조건일 뿐 fresh native identity가 아니다. 원 response proof에 묶인 Esc 한 번 뒤 새 status로만 native identity를 확인한다. cleanup-only card의 UUID/cwd와 새 status의 연속성도 대조하며, 불일치 시 native/attestation을 채택하지 않는다. card에서 권한이나 launch version을 추론하지 않는다.

`runtime_refresh`는 관측 native319/329/330/331 bypass와 launch330/331을 별도로 제한한다. 기존 native319의 null mode를 변경하지 않고 동일 UUID/cwd/권한의 fresh mode와 response proof를 별도 attestation/event에 저장한다. execute·owned launch·재개 후 대조는 같은 선택 함수를 사용한다. attestation이 없거나 identity/proof/event가 맞지 않으면 legacy null mode로 launch할 수 없다. argv·권한·예외·부재/중복 가드는 유지한다.

fresh331 placeholder는 실제 관측된 create-util/how-does 두 문구와 정확한331 visible header, 기존 empty draft guard만 허용한다. root의 owned331 evidence에서 빈/restored frame은 draft 키가 생략됐고, 두 문구를 각각 직접 입력하면 별도 nonempty draft가 있었다. 초기의 “명시 empty draft 키 필요” 가정을 이 실제 관측으로 정정한다. 키 생략·null·빈 문자열은 기존 empty guard로 처리하며, typed-identical draft·일반 Try 문구·다른 버전·header 부재는 거부한다.

## 결과와 완료 판단

가짜 transport·임시 signed Store의 source 회귀는 실제 native canary·호스트 복구·배포의 증거가 아니다. native319/329/331 canary, same-UUID331 migration과 typed-identical negative의 실제 완료 판정은 별도 root 검증 기록을 따른다. 이 구현자는 원격 작업·버전 변경·조립·설치·Git publication을 실행하지 않았다. 공유 workspace의 UUID 불명 예외는 이후 cold restore를 계속 차단할 수 있다. Orca inventory/관측과 입력·create 사이의 비원자 경합도 남는다.
