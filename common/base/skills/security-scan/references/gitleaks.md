# Gitleaks 커밋과 전송 검사

staged 내용, 전송 commit의 비밀 또는 등록된 로컬 전용 산출물을 검사할 때 읽는다. 탐지는 [Gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)을 재사용하고, 자체 코드는 명시 등록, 산출물 정책, Git 및 제품 adapter 연결만 담당한다.

## 입력과 전제

저장소 root, Git의 실제 hooks 경로, 기존 hook 및 관리자, 안정적인 외부 runtime 경로와 신뢰할 Gitleaks 실행 파일을 확인한다. 버전과 Linux x64 archive checksum은 [manifest](../../../scripts/dev-tools.toml)가 소유한다. 설치와 등록은 검사 중 자동 수행하지 않는다.

로컬 전용 경로는 각 저장소의 `--local-only 'evidence/**'`처럼 명시한다. 패턴은 저장소 상대 경로에 Python fnmatch를 적용하며 `*`는 `/`도 포함한다. `runs/`를 전역 금지하지 않는다. `--allow-artifact`는 root가 실제 Git root인 `tr-local-docs` 백업에만 허용하며 `_bmad-output/**` 또는 명시 하위 경로의 같은 suffix만 받는다. 이 예외도 비밀 검사를 생략하지 않는다. 백업 원격과 공유 권한 확인은 등록 전에 별도로 한다.

## 수행 방법과 절차

1. source의 `scripts/setup_git_guard.py --prefix NEW_DIRECTORY`로 Gitleaks만 격리 설치한다. 공식 release archive checksum을 검증하며 호스트 설정이나 hook을 활성화하지 않는다. 런타임은 다운로드하지 않는다.
2. `python3 scripts/git-guard-install.py plan --repo REPO --state NEW_EXTERNAL_STATE --gitleaks /absolute/gitleaks --local-only 'evidence/**'`를 plugin root에서 실행한다. 실제 파일, 원본 백업 여부와 새 bytes의 hash, hooksPath 설정과 버전을 제시한다. live 적용 전에 이 변경 범위와 백업을 확인한다.
3. 확인된 같은 인자로 `plan` 대신 `apply`를 실행해 명시 등록한다. 안정 runtime에는 engine, scanner 사본, 로컬 정책과 원본 bytes/modes/config receipt를 둔다. plugin cache 갱신으로 이 runtime을 제거하지 않는다. `install.sh`의 native plugin 설치와 Git 등록은 별개다.
4. 필요하면 `python3 scripts/commit-guard.py index --repo REPO --policy STATE/policy.json`로 staged 검사를 직접 실행한다. 실제 Git pre-commit/pre-push는 agent 종류와 무관하게 동작한다. PreToolUse는 보이는 blanket staging 및 hook 우회에 조기 피드백을 주며 shell을 실행하거나 완전히 해석하지 않는다.
5. `python3 scripts/git-guard-install.py status --state STATE`로 managed 파일과 hooksPath 변경을 확인한다. 복구가 필요하면 아래 실패와 복구를 적용한다.

검사 후보의 정확한 bytes를 권한 0700 임시 디렉터리 아래 0600 일반 파일로 저장하고 index 또는 전체 outgoing 범위당 Gitleaks `dir`를 한 번 실행한다. 논리 경로와 무관한 중립 파일명으로 filename allowlist에 의한 누락을 방지한다. 신뢰 설정·빈 ignore·redacted report는 payload 밖에 두며, report의 알 수 없는 경로와 잘못된 형식은 차단한다. 비밀 내용과 scanner 출력을 공개하지 않고 자체 임시 자료만 정리한다. 큰 이력과 대형 파일은 여전히 시간·메모리·임시 디스크 비용이 있다.

Go 의존성의 `go.sum`은 전체 파일을 제외하지 않는다. 해당 후보의 중립 파일명과 정규형 Go SHA256 체크섬 한 줄을 함께 만족할 때만 Gitleaks `generic-api-key` 규칙의 allowlist를 신뢰 설정에 추가한다. 기본 규칙 상속과 `condition = "AND"`를 재사용하며 다른 서비스 토큰 규칙, 추가된 줄과 비정상 체크섬은 계속 검사한다. 원본 bytes와 다른 파일의 검사는 유지한다. 이는 체크섬의 형식 판별이며 실제 의존성 무결성 검증을 대신하지 않는다.

후보 blob은 경로로 조합한 revision 대신 index·tree의 mode와 object ID로 읽는다. gitlink는 기록된 commit 포인터만 검사하며 submodule 작업 트리나 내부 object를 읽지 않는다. submodule 내용은 해당 저장소를 별도로 등록해야 검사된다. 로컬 전용 경로 정책은 gitlink 경로에도 적용한다.


Git pre-commit은 index의 추가 및 변경 blob만 검사하며 unstaged 변경을 읽지 않는다. 삭제는 검사할 새 blob이 없다. pre-push는 stdin의 모든 ref update를 검증하고 outgoing commit마다 변경된 blob과 commit message를 검사한다. 새 branch와 commit tag는 알려진 로컬 이력을 검사하며 deletion은 허용한다. 비 commit object, 없는 base, shallow 이력과 알 수 없는 범위는 fetch 없이 막는다. annotated tag object의 message도 검사한다.

기존 실행 가능한 pre-commit/pre-push는 최초 guard 통과 뒤 같은 argv와 pre-push stdin으로 체인한다. 기존 pre-commit이 성공하면 변경된 최종 index를 다시 검사해 그 hook이 추가한 비밀과 로컬 전용 산출물도 차단한다. 기존 hook 실패는 그대로 반환하며 실패 뒤 재검사는 실행하지 않는다. pre-push는 최초 검사와 기존 hook 실행 순서만 사용한다. 다른 이벤트와 core.hooksPath를 수정하지 않는다. hook의 실행 경로 이름은 `.tr-kit-original`로 바뀌므로 원래 basename 자체에 의존하는 hook은 수동 호환 확인이 필요하다. 알려진 관리자와 symlink hook은 거부한다. 공유 hooks 경로의 미등록 worktree는 기존 hook만 실행하며 별도로 등록해야 한다. 같은 공유 hooks 경로에 두 번째 guard 등록은 충돌로 거부하므로 별도 hooks 경로 구성이 필요하다.

## 제약과 주의점

신뢰된 절대 scanner 사본, 내장 기본 규칙을 확장한 임시 config, 빈 ignore 파일과 `--ignore-gitleaks-allow`를 사용한다. repo의 `.gitleaks.toml`, ignore, inline allow 및 `GITLEAKS_*` 환경변수로 검사를 끄지 못하게 한다. scanner stdout/stderr와 발견 원문은 공개하지 않으며 receipt에 findings를 저장하지 않는다. 누락, 오류와 timeout은 발견 사항과 구분해 차단한다.

로컬 hook과 PreToolUse는 사용자가 우회하거나 수정할 수 있으며 전체 보안 경계가 아니다. binary, 압축 및 인코딩된 payload에 대한 완전 탐지나 소유권 판정을 보장하지 않는다. 제품 hook은 packaging의 명시 opt-in과 해당 제품의 trust/활성 설정이 필요하다. 기존 Orca 및 다른 plugin hook을 교체하지 않는다.

### Native 도구 입력과 완료 출력 보호

양 adapter의 PreToolUse는 모든 도구의 literal 입력을 같은 `scan(blobs, scanner)`로 검사한다. 알려진 전체 환경 출력(`env`, 인자 없는 `printenv`, `export -p` 등)과 인증 원본 파일 읽기(`auth.json`, `.credentials.json`, `.env` 등)는 실행 전에 거부한다. shell은 실행하거나 완전히 해석하지 않는다. 정상 `env NAME=value command`, `printenv PATH`, 존재, 권한, hash 조회와 `.env.example`, sample, template 읽기는 보존하며 입력의 실제 비밀은 scanner가 별도로 검사한다. 인용 소스의 단순 문구를 실행 명령으로 취급하지 않는다. 동적 구성, 다른 언어와 모든 우회 구문을 포괄하지 않는다.

Native scanner는 `~/.local/share/tr-kit/gitleaks/<manifest version>/bin/gitleaks`만 사용한다. 같은 prefix의 `provisioned.json`에 version, manifest의 archive SHA256, 실제 executable bytes와 일치하는 binary SHA256이 있어야 한다. PATH, repo config나 별도 Git 등록 정책으로 이를 대체하지 않는다. 설치는 위 `setup_git_guard.py --prefix ~/.local/share/tr-kit/gitleaks/<version>`로 새 prefix에만 수행하며 누락 시 hook이 설치하지 않는다. native 모드에는 Python 3.11 이상의 표준 `tomllib`가 필요하다. 설치 전 `python3 --version`과 scanner receipt를 확인하며 Codex installer도 hook payload의 Python 버전을 검사한다. 기존 단일 engine의 index/push는 Python 3.10에서 import 가능한 계약을 유지한다.

PostToolUse 검사 도구는 shell(`Bash`, `exec_command`, `write_stdin`), 파일, 검색, 편집(`Read`, `read_file`, `Write`, `Edit`, `MultiEdit`, `Glob`, `Grep`, `NotebookEdit`, `apply_patch`), `WebFetch`/`WebSearch`, MCP resource 도구(`list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource`)와 `mcp__<server>__<tool>` 이름의 MCP 호출이다. 이 목록 밖의 도구는 adapter matcher에 연결하지 않으며 미지원이다. `tool_response`/`tool_result`/`tool_output`/`error` envelope를 검사하고, 발견 시 Codex는 `decision: "block"`과 고정 `reason`으로 원본 tool result를 대체한다. Claude는 `hookSpecificOutput.updatedToolOutput`에 Bash의 stdout/stderr/interrupted/isImage 객체, Read text의 type/file 객체 또는 MCP의 고정 알림 문자열을 반환한다. MCP의 원본 string, content-block array, plain-object variant를 모두 지원한다. Claude 다른 local 도구나 Read의 비텍스트 variant는 교체 schema가 미확인이므로 발견 시 미지원 안내와 `continue: false`로 중단하며 원본 은닉 성공으로 보고하지 않는다. stdout과 stderr를 따로 공개하지 않는다. clean 결과는 원래 계약을 유지한다. scanner 오류, 누락, timeout, 크기 초과는 지원하는 제품, 도구의 고정 block/교체 응답과 `continue: false`로 중단하며 탐지 성공과 구분한다. 파싱 불가, 전체 stdin 초과로 tool schema를 모르면 Codex는 고정 block, Claude는 미지원 중단으로 구분한다. 알 수 없는 결과 계약도 중단한다. stdin과 직렬화한 입력, 결과는 각각 8 MiB 한도이며 scanner의 35초 subprocess budget보다 큰 45초 hook timeout을 사용한다. 오류에 payload나 scanner 원문을 싣지 않는다.

Claude의 PostToolUseFailure도 결과, 오류 본문을 먼저 검사하고 clean 실패는 `{}`로 계속 전달한다. 비밀 발견이나 검사 실패 시 결과 교체 지원을 보장하지 못하므로 원문을 담지 않은 고정 안내와 `continue: false`로 중단한다. 이를 마스킹 완료로 보고하지 않는다. Codex에는 이 event를 등록하지 않으며, 실패한 shell도 PostToolUse 결과 계약으로 처리한다. Codex의 완료 후 PostToolUse는 이후 write_stdin poll에서 전달될 수 있고 write_stdin 자체는 PreToolUse를 거치지 않는다. 초기 중간 출력, 백그라운드 출력, code-mode 중간 경로와 미지원 도구의 원문 보호는 보장하지 않는다. 제품별 native canary로 완료 출력의 실제 모델 전달과 화면 표시를 각각 검증한다. 응답 형식의 근거는 [Codex PostToolUse](https://learn.chatgpt.com/docs/hooks#posttooluse), [Claude PostToolUse](https://code.claude.com/docs/en/hooks#posttooluse-decision-control), [Claude SDK Tool Output Types](https://code.claude.com/docs/en/agent-sdk/typescript#tool-output-types)이며 문서 계약과 실제 native 검증은 구분한다.

후처리는 이미 실행된 부작용, 제품의 원본 transcript/telemetry와 기존 기록을 소급 제거하지 못한다. 교체된 모델 전달 값과 화면, 제품 원본 기록, 병렬 개인 capture의 저장 경계는 서로 구분한다. 개인 capture는 private admission에서 native 결과, 오류 본문을 제외하며 이 공통 hook에 private 연결을 추가하지 않는다. 모든 secret, 도구를 막는 보안 경계로 설명하지 않는다.

## 결과와 완료 판단

버전, 대상 index 또는 outgoing 범위, 발견과 검사 오류, 실제 검사 및 미지원 범위를 구분한다. fixture에서 clean/secret, partial stage, backup 예외, 기존 hook 실패, 실제 local bare remote push와 rollback을 검증한다. adapter JSON 단독 성공은 제품 native canary 성공이 아니다. 양 제품에서 benign 실행과 unsafe 실행 전 deny를 관측하고 callback 오류를 별도로 확인해야 해당 수용 조건을 완료로 판단한다.

## 실패와 복구

검사가 막히면 staged diff 또는 등록 경로를 검토하고 승인된 대상만 수정한다. 자동 stage/unstage/reset/delete, hook 우회, history rewrite와 production push를 수행하지 않는다. scanner 오류는 도구 상태를 고친 뒤 다시 검사한다.

`python3 scripts/git-guard-install.py rollback --state STATE`는 모든 managed bytes/modes와 core.hooksPath가 receipt와 일치할 때만 원본을 복원한다. 나중 편집이 있으면 아무 파일도 덮지 않고 conflict를 보고한다. 원본과 receipt를 보존한 채 차이를 먼저 해소한다. runtime 디렉터리와 receipt는 복구 근거로 남는다.
