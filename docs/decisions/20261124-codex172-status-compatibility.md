# Codex0.172.0과 status 시간·crop 호환

승인된 native CLI 업데이트/세션 보존과 R-52~R-55를 따른다. 계획은 로컬 `plan-codex-0172-supported-session-resume.md`, source baseline은 `fa660f9cd9a820c267aee1091621ba5ca4d80a1d`다. 공식0.172.0 release와 npm 설치를 확인했고 권한 보존을 지원하는 exact 버전만 기존 allowlist에 추가한다. 다른 patch/future 버전이나 unknown/default/Custom 모드는 계속 거부한다. [공식 release](https://github.com/openai/codex/releases/tag/rust-v0.172.0)의 exec-resume 설명을 TUI 재개 성공으로 확대하지 않는다.

NAS의 기존 full passive guard와 coherent stream 읽기는 각각2.709s/0.414s였다. 사용자 승인에 따라 Codex status 응답 제한만3→15초로 바꾸며60회·0.05초 간격, 개별 CLI timeout, Claude의 별도3초 제한과 모든 신원·상태·stream·최종 proof 검사를 유지한다. 같은 요청을 재전송하지 않는다.

관측된 cropped repeat에는 startup 뒤 원래4번째 줄에 있던 첫 일반 요청문이 화면 맨 위에 고정되고, 이전 Session 줄을 포함한 연속 suffix가 남았다. 기존 첫 줄 전용 pin을 첫 일반 요청문의 정확하고 유일한 보존으로 확장하는 것을 사용자가 승인했다. 상세 단일 계약은 [runtime-refresh](../../common/base/skills/session/references/runtime-refresh.md#codex-status-응답-대기와-수신자-home)에 둔다. 나중 요청문·slash echo·중복·이력 변경·새 경계·다른 UUID/권한·동일 화면은 대신 허용하지 않는다.

기존 소유 시험의3초 실패와 후속 freshness 실패, signed Store/key/선택/event를 보존한다. crop 보완 뒤에도 같은 화면과 같은 cursor만 나오는 기존 반복은 의도대로 미확인이다. 별도 기본 launch 조건의 새 소유 canary는 그 기존 배치의 복구 성공으로 간주하지 않는다. 실제 resume 통과 전에는 새 호환성을 운영 검증 완료로 보고하거나 배포하지 않는다.

파일 배치와 외부 의존은 그대로다. 기존 `session → native_query/codex_screen_status → Store/Recorder와 resume_command`를 재사용하며 새 skill/hook/adapter·위임기를 추가하지 않는다. 원문·설치본은 수정하지 않으며 원본 사용자 세션과 수동 예외를 입력/종료/launch 시험 대상으로 삼지 않는다. source/fake/native/설치와 소비의 검증 결과는 [검증 기록](../verification.md#codex01720과-status-시간crop-호환--2026-11-24)에서 구분한다.
