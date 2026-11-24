# 수동 예외 신원 보존과 Claude331 활성 목록

승인 계획 `plan-session-exception-identity-and-listing.md`(baseline `0b85f9a75d2d4d2752c4647fd831a439c883c04c`)의 frozen intent를 따른다. 알려진 수동 예외 pane를 workspace 전체 차단과 구분하고, 관측 native331의 `✔ on`만 기존 활성 목록 검증에 연결한다. 실제 운영·배포·PC reboot 승인을 추가하지 않는다.

기존 Store/key/서명/binding·선택/수동 상태·historical native/null·events prefix를 보존한다. 별도 명시 `identify-exception`은 원 manual Claude 행과 유일한 현재 공식 신원을 결합해 signed event-bound attestation만 추가한다. 새 helper는 공식331 `agents --json`을 기존 bounded transport로 사용하고 실제 UID/start/executable/cwd/pane/PID namespace를 전후 확인한다. name/status/startedAt은 authority에서 제외한다. 과거 PID는 재부팅 뒤 authority가 아니며 같은 UUID/원 pane/workspace의 새 live proof만 operation 동안 고정한다. unknown/중복/바뀐 proof는 입력·create 전에 중단하고 manual/self에는 terminal 입력이나 화면 조회를 하지 않는다.

`runtime_refresh`의 기존 guarded 경계가 선택 회복의 proof callback도 대조한다. 긴 공식 조회는 최종 선택 frame 관측보다 앞에 둔다. 예외가 있는 create는 durable sending 뒤 공식 UUID를 확인해 저장 중 같은 PID의 대화 전환도 거부하고, 기존 모달/frame·management 증명은 그대로 대조한다. 예외가 없는 create의 기존 receipt 순서는 유지한다. 비원자 공식 관측/frame/create 사이의 경합은 제거하지 못한다.

listing parser는 optional actual-native-version을 받고 real refresh caller가 fresh before.nativeVersion을 전달한다. 기존 enabled 문법과 ID/scope/중복/누락 검증 및 stale-listed-version 진단은 유지하며 설치 버전만으로331 문법을 활성화하지 않는다. 운영 세부 조건은 [단일 session 계약](../../common/base/skills/session/references/session-restart.md#명시-수동-예외의-신원-확인과-재검증), [runtime 계약](../../common/base/skills/session/references/runtime-refresh.md#수행-방법과-절차), 파일/호출 관계는 [구조](../architecture.md#수동-예외-신원과-claude331-활성-목록--2026-11-24)를 참조한다.

source/fake proc/transport 검증과 root의 별도 native·패키지·운영 검증은 [검증 기록](../verification.md#수동-예외-신원과-claude331-활성-목록--2026-11-24)에서 분리한다. 실제 reboot는 미실행이며 새 boot/PID 동작은 소유 fixture 결과로만 판정한다.

## Cold-start 누락 보완

Root가 원 재부팅/수동 예외 유지 요구를 계획의 non-frozen Change Log/Clarified Cold-Start Verification에 대조하고, 선택과 manual이 모두 부재인 소유 fixture의 기존 보류를 재현했다. Live-only 선택이 만든 수동 선행 의존을 제거하기 위해, historical attestation이 있는 manual의 엄격한 known-absent 증명만 추가했다. 원 pane/연관 및 ps-only agent가 complete Orca 뷰에 없고, 두 공식 active JSON 전체에 expected UUID가 없으며 다른 cwd를 포함한 active proc 전체가 bounded 지원 증명으로 전후 일치하고 원 pane를 재사용하지 않을 때만 허용한다. cold의 unreadable process는 부재 거부이며 live의 unrelated-cwd 무조회는 유지한다. unreadable/다른 UUID·pane 재사용/nonagent·unknown 존재는 부재로 취급하지 않는다.

Absent 판정·원 UUID/pane/workspace와 producer/query 실행체는 invocation 동안 고정하며, 관련 선택 process의 정상 create는 그 부재 identity를 변경하지 않는다. 기존 live proof와 historical attestation을 absent로 덮어쓰거나 한 operation 안에서 live/absent를 재기준화하지 않는다. 공식 조회 뒤 complete Orca를 다시 읽고, native preflight를 최종 selected inventory/frame 앞에 둬 그 긴 조회 중 생긴 후보도 거부한다. 선택/권한/수동 무입력·원본 보존·actual reboot 미승인 경계는 유지한다.

## 검증한 producer와 실제 실행체의 결합

Quick 검수에서 caller cwd의 상대 PATH로 검증한 공식 producer와 target cwd에서 bare `claude`로 실행한 파일이 달라질 수 있음을 root의 소유 fixture로 재현했다. 수정 계획의 Producer Binding Correction에 따라 기존 bounded runner에 내부 optional `executable`을 추가한다. 전달한 canonical absolute regular executable만 실행하며 기본 호출은 보존한다. helper는 검증한 queryExecutable.path를 version과 두 agents 조회에 전달하고, 각 호출 전후 및 최종 proof 경계에서 같은 파일 identity를 확인한다. 바뀐 파일·실패한 producer는 중단하며 PATH의 다른 실행체로 fallback하거나 proof를 재기준화하지 않는다. timeout/output/진단/stdin 격리/group cleanup은 기존 runner가 계속 소유한다.

교정 전268개 candidate 결과는 과거 보존 근거이며 최종 인증으로 재사용하지 않는다. 같은 cwd 차이의 실제 소유 subprocess 시험과 새 교정 뒤 전체 affected suite의 결과를 검증 기록에 따로 남긴다. 이 변경은 attestation/history·cold/live proof·선택 권한이나 native331 listing 범위를 확대하지 않는다.
