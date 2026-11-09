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

## 결과와 완료 판단

버전, 대상 index 또는 outgoing 범위, 발견과 검사 오류, 실제 검사 및 미지원 범위를 구분한다. fixture에서 clean/secret, partial stage, backup 예외, 기존 hook 실패, 실제 local bare remote push와 rollback을 검증한다. adapter JSON 단독 성공은 제품 native canary 성공이 아니다. 양 제품에서 benign 실행과 unsafe 실행 전 deny를 관측하고 callback 오류를 별도로 확인해야 해당 수용 조건을 완료로 판단한다.

## 실패와 복구

검사가 막히면 staged diff 또는 등록 경로를 검토하고 승인된 대상만 수정한다. 자동 stage/unstage/reset/delete, hook 우회, history rewrite와 production push를 수행하지 않는다. scanner 오류는 도구 상태를 고친 뒤 다시 검사한다.

`python3 scripts/git-guard-install.py rollback --state STATE`는 모든 managed bytes/modes와 core.hooksPath가 receipt와 일치할 때만 원본을 복원한다. 나중 편집이 있으면 아무 파일도 덮지 않고 conflict를 보고한다. 원본과 receipt를 보존한 채 차이를 먼저 해소한다. runtime 디렉터리와 receipt는 복구 근거로 남는다.
