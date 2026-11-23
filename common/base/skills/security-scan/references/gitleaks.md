# Gitleaks 커밋과 전송 검사

## 목적과 역할 경계

- staged·outgoing 비밀 및 저장소별 명시 산출물 정책 검사는 공식 Gitleaks와 자체 Git 연결로 수행한다.
- 직접 검사 CLI, 비활성 hook renderer와 명시 등록·기존 hook 연결·status/rollback 관리기가 있다. source 작성·검사 요청을 실제 저장소의 hook 활성화 승인으로 취급하지 않는다.

## 입력과 전제

- 실제 Git root, 검사 모드, 등록 정책 파일과 승인된 검사 범위를 받는다. `common/base/scripts/secret-tools.toml`의 Gitleaks pin을 사용한다.
- Git 정책은 `gitleaks`의 신뢰한 절대 실행 경로와 `repositories` 배열을 갖는다. 각 항목은 실제 `path`, `local_only`와 `allow_artifacts` 문자열 배열이다. 해당 실제 Git root가 정확히 하나 등록돼야 한다.
- 기존 등록·scanner 신뢰 근거를 재사용한다. 임의 바이너리·PATH 결과를 신뢰 경로로 등록하지 않는다. 정책 파일 부재는 검사 완료가 아니며 자동 등록하지 않는다.
- Gitleaks 준비가 별도로 요청된 경우만 [공식 도구 준비·확인](../../../references/toolchain.md)의 Gitleaks group을 연결한다. 준비와 저장소 등록/활성화는 별개다. 일반 검사 실패를 자동 설치나 새 등록으로 해결하지 않는다.
- index/outgoing 검사의 필수 정책·scanner·검사용 임시 파일 쓰기 조건을 충족하지 못하면 해당 검사를 미실행/검사 불가로 보고한다. 원본 파일을 읽을 수 있거나 같은 Gitleaks 바이너리가 있다는 이유로 `stdin`·직접 `git`/`dir` 모드 등 다른 호출로 정해진 검사를 대체하지 않는다. 임시 파일 생성도 제외한 요청이면 그 경계를 유지하고, 독립적으로 가능한 등록 plan만 계속할 수 있다.
- `local_only`와 예외는 저장소 상대 Python fnmatch 패턴이다. `*`는 `/`도 포함한다. `runs/`를 이름만으로 금지하지 않는다. 백업 예외는 사용자가 승인한 실제 `tr-local-docs` Git root에 한정하고 패턴 끝 두 요소가 정확히 `_bmad-output/**`여야 한다. 상대경로의 빈 요소·점·상위 경로·역슬래시는 거부한다. 등록기와 engine 모두 검사하며 원격·공유 승인까지 확인한 것으로 확대하지 않는다. 예외 파일도 비밀 검사를 수행한다.
- 관리기가 생성하는 정책은 `scanner_sha256`을 포함한다. 매 Git 검사 시 명시 scanner의 provision receipt·pin·binary hash와 등록 당시 hash를 확인한다. 기존 수동 검사 정책의 호환 입력에는 이 필드가 선택이지만 공식 설치/신뢰 확인 책임은 유지한다.

## 수행 방법과 절차

1. kit source root에서 `python3 -B scripts/check-git-secrets.py index --repo /absolute/repo --policy /absolute/policy.json`으로 index를 검사한다. unstaged 자료를 검사했다고 보고하지 않는다.
2. push 검사는 같은 CLI의 `push` 모드를 사용한다. stdin은 실제 Git pre-push의 모든 ref update 네 필드 형식이다. 실제 outgoing 범위를 알 수 없으면 임의의 HEAD 검사로 대체하지 않는다. 직접 검사 자체는 전송하지 않는다.
3. JSON `status`는 `pass`, `finding`, `policy_violation`, `unavailable`로 구분된다. 실패는 exit 2다. 비밀 원문·scanner 출력 없이 안전한 규칙 식별자·건수만 전달한다.
4. `scripts/render-git-secret-hook.py`는 명시 mode·source-root·repo·policy·python으로 **비활성 shell 텍스트만** 출력한다. 등록·체인·복구를 구현한 것으로 취급하지 않는다. 제품 hook 텍스트는 `scripts/render-secret-hook.py`가 제품별 template에서 출력한다.
5. 실패 시 staged diff·정책·범위를 확인하고 승인된 대상만 수정한 뒤 같은 범위를 재검사한다. 자동 stage/unstage/reset/delete, 우회 flag, 이력 재작성이나 production push로 해결하지 않는다.

### 등록·상태·복귀

- 단순 검사와 별개 요청이다. 승인받은 실제 repo·scanner 절대경로와 worktree/Git/hooks 밖 신규 state를 받는다. state의 부모 디렉토리는 존재해야 한다. 실제 기존 hook과 변경 범위·공유 hooks 영향을 먼저 대조한다.
- kit root에서 `python3 -B scripts/git-guard-install.py plan --repo /absolute/repo --state /absolute/new-state --gitleaks /absolute/provision/bin/gitleaks`를 사용한다. 필요한 저장소별 패턴만 `--local-only 'evidence/**'`처럼 명시한다. 백업 예외는 승인된 경우에만 `--allow-artifact 'project/_bmad-output/**'`로 추가한다. pattern은 shell 확장을 막도록 인용한다.
- plan은 파일을 쓰지 않고 경로·변경 hash·plan_id를 출력한다. 승인 범위와 확인된 변경이 맞으면 같은 인자를 사용하는 `apply`에 `--expect-plan <plan_id>`를 추가한다. 입력·source·기존 hook/설정이 달라지면 거부한다. 매 명령마다 새 사용자 승인을 요구한다는 뜻이 아니다.
- `python3 -B scripts/git-guard-install.py status --state /absolute/state`로 소유 파일·hook 설정과 scanner 상태를 확인한다. `active`는 등록 상태이며 실제 모든 제품·인프라 안전 판정이 아니다.
- `rollback --state /absolute/state`는 소유 변경을 기존 bytes/mode로 되돌린다. 사후 편집·경로/설정 변경이면 강제 덮어쓰지 않는다. 이미 복귀한 receipt는 다시 적용하지 않으며 재등록은 새 계획/state로 처리한다.
- 원래 hook이 있으면 argv·pre-push stdin·실패를 유지하고 실행 전후에 등록 root를 검사한다. 실행 불가 mode의 원래 hook은 실행하지 않는다. 기존 hook이 staged 내용을 바꿨다가 재검사에서 실패해도 staged 변경을 자동 복구하지 않는다.
- 알려진 외부 hook manager·기존 tr-kit 등록·symlink·점유 backup은 거부한다. Git 설정을 바꾸거나 다른 worktree를 자동 등록하지 않는다. 공유 hooks를 쓰는 다른 worktree에서는 기존 hook만 유지한다. 임의 hook의 `$0`/자체 파일명 의존은 이 연결로 호환을 보장하지 않는다.
- 부분 실패는 write journal·원래 bytes/mode로 복귀하며 충돌/복구 불가를 알린다. 정상 복귀 뒤 로컬 receipt는 남는다. 원래 hook 사본을 포함하므로 receipt를 source/공유 로그에 커밋하지 않는다. 외부 scanner가 사라져도 소유 파일에 충돌이 없으면 복귀할 수 있다.

## 제약과 주의점

- Gitleaks v8.30.1 공식 [도구 설명](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)과 설치 pin을 재사용한다. 외부 바이너리·원문을 kit에 동봉하지 않는다.
- Git 후보는 index/tree object bytes를 검사한다. gitlink는 포인터만 검사하며 submodule 내용은 별도 대상이다. outgoing commit·tag message를 포함하며 shallow·불명 범위는 fetch 없이 보류한다. 삭제 ref에는 새 payload가 없다.
- `go.sum` 전체를 제외하지 않는다. 중립 후보 이름과 정규형 SHA256 체크섬 줄을 함께 만족하는 `generic-api-key` 예외만 적용하고 다른 규칙·추가 줄·비정상 체크섬은 계속 검사한다. 이 형식 판별은 의존성 무결성 증명이 아니다.
- 검사마다 중립 파일명·별도 임시 config·빈 ignore를 사용한다. 저장소 설정·inline allow·`GITLEAKS_*`로 검사를 약화하지 않는다. scanner 오류·timeout은 발견과 구분해 차단한다. 전체 Git 이력의 총 자원 한도는 아직 없으며 개별 subprocess timeout과 다르다.
- 제품 native 입력·출력 adapter는 별도 신뢰 receipt의 Gitleaks를 사용한다. 실제 이벤트·출력 교체·trust·다른 hook과의 활성 조합은 최종 통합 검증 대상이다. 합성 JSON 통과를 실제 화면/모델 출력 보호로 확대하지 않는다. Codex `write_stdin`에는 PreToolUse 재호출이 없으며 code-mode·중간 출력과 모든 인코딩 payload를 포괄하지 않는다.
- Post 검사는 실행 부작용·제품 원본 기록을 소급 제거하지 않는다. Git hook도 우회 가능하며 공유·반출 판단을 대신하지 않는다.

## 결과와 완료 판단

- 대상·scanner pin·index/outgoing 범위, 발견·검사 오류·산출물 정책 위반을 구분한다.
- CLI 실행, 임시 Git hook 실행, 제품 adapter 합성, 실제 제품 native·활성 조합을 별도로 보고한다. source의 지원·미이관 상태는 `docs/verification.md`에서 확인한다.
