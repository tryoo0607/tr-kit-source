# Codex0.172.0 scrollback과 단일 준비 턴

## 요구와 결정

승인 계획 `plan-codex172-resume-observation.md`는 사용자 `자동 확인 턴까지 포함해 반영·검증 계속` 승인(call_421e8e09f48048d0849f31abf90e701b)을 근거로, 설치된 Codex0.172.0의 exact UUID 재개에 공식 inline 화면과 고정 준비 메시지 한 번을 추가한다. baseline은39676f6e4c916e61e2fc8a7cfcefbfbda6b337ef다. 기존 zsh process/정상 종료 증명과 role·runtime·inventory·self·draft·busy·child·permission·UUID·cwd·version·deadline·단일 입력·서명 receipt 가드를 보존한다. 설치본·upstream·hook trust·전역 설정·private 구현 복사는 변경하지 않는다.

공식0.172.0 tag commit `3d86e43b075adeba2193ec5c22ac92f55afd82e6`의 [CLI 선언](https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/tui/src/cli.rs#L16)은 PROMPT와 scrollback을 보존하는 `--no-alt-screen`을 제공한다. [session 초기화](https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/session/session.rs#L2169)는 resume의 SessionStart source를 pending으로 넣고, [모델 turn](https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/session/turn.rs#L412)은 pending hook을 실행한다. [prompt header](https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/tui/src/transcript_view/prompt_header.rs#L1)는 presentation-only이며 transcript 내용이 아니다. 이 문서의 공식 source 확인은 로컬 `codex0172-render-research/`의 원문 snapshots와 URL/hash 목록을 대조한 정적 확인이며 native 동작 시험과 구분한다.

공통 `resume_command`와 `native_query`만 보완한다. strict prototype `1f6159…`를 기준으로 기존 native runner와 Store/Journal을 재사용한다. 반복 상태 조회에서 남은 자동완성 오탐은 알려진0.172.0 `/status`의 물리 입력 끝에 공백 하나를 붙여 메뉴를 닫는 방식으로 예방한다. 현재 runtime SHA256은 `77cef6e0b238708b2ac56fb2ef5499b1de8c59c4ba44e14642dff9c227dea052`다. [공식 command token 처리](https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/tui/src/bottom_pane/chat_composer/slash_input.rs#L594)는 caret이 명령 끝을 지나면 popup 대상을 반환하지 않으며, 제출 공백 제거로 명령 의미는 유지된다. 입력 횟수와 기존 출력 검사는 바꾸지 않는다. 새 준비 PROMPT는 새 사용자 메시지·모델 실행·토큰 사용을 뜻하며 도구 금지는 모델 지시다. 기존 Full Access 모드의 옵션과 다른 지원 버전·Claude argv는 보존한다. 알 수 없는 버전·권한·실패를 자동 재전송으로 해소하지 않는다. 구체적인 지원 formatter와 필터 정본은 [운영 계약](../../common/base/skills/session/references/runtime-refresh.md#codex01720-scrollback과-단일-준비-턴)이다.

## 검증과 한계

portable semantic 시험으로 정확한 버전별 argv·외부 flags/PROMPT 무시·기존 거부·home 축약과 bounded UI의 정상/거부를 확인한다. scratch 절대 경로에 의존하는 prototype AST 시험2개는 source 테스트로 복사하지 않는다. 해당 baseline 보존 대조는 로컬 일회성 감사 receipt로만 남긴다. native source 일치·full common CI와 배포 상태는 [검증 기록](../verification.md#codex01720-scrollback과-단일-준비-턴--2026-11-25)을 따른다.

이전 넓은 prototype `12b5`의 NAS 정상 재시작2회와 반복 verify는 과거 근거다. strict formatter 보완 뒤 raw stream replay 통과와 구분하며 이전 native2를 strict-source native2로 바꾸어 표기하지 않는다. 실패 Store·키·이력은 유지한다. 실제 hook/model/input/identity 미확인은 완료로 보고하지 않는다. readiness reply·plugin inventory·native 재개는 plugin 소비의 증명이 아니며 소비는 독립 증거 없으면 unverified/null이다. 부모가 source native, private pin/package·원격 전송·publication/deploy와 원래 사용자 배치를 별도 담당한다. root dev01은 수동, inno는 common-only이고 실제 PC reboot는 이 구현 시험 범위가 아니다.
