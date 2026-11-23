# 시크릿·커밋 검사 hook 개편

## 근거와 범위

사용자는 기존 원문 보호 hook 검수 뒤 시크릿·커밋 검사도 수정→구현·검수하고 나머지 기능/skill 이관으로 넘어가도록 요청했다. [기존 사례 조사](20261117-secret-guard-findings.md)의 조사 단계에서 구현 단계로 진행한다. scratch만 변경하며 기존 설치본·Git 등록·신뢰·배포·Sites 재호출은 변경하지 않는다.

## 재사용과 책임

Gitleaks8.30.1 공식 설치 바이너리를 외부 실행으로 사용한다. 새 kit에 외부 소스·바이너리를 동봉하지 않는다. 기존 자체 commit-guard의 Git 후보 읽기·검사기 연결·literal 검사만 재사용하며 공통 검사와 제품 반환 계약을 나눈다.

```text
common/base/scripts/
├── secret_guard.py
└── secret-tools.toml
adapters/
├── codex/
│   ├── scripts/secret_guard.py
│   └── hooks/secret-guard.json.in
└── claude/
    ├── scripts/secret_guard.py
    └── hooks/secret-guard.json.in
scripts/
├── check-git-secrets.py
├── render-git-secret-hook.py
└── render-secret-hook.py
tests/
├── test_secret_legacy.py
├── test_secret_git_hook.py
└── test_secret_revision.py
```

```text
PreToolUse → 제품 adapter → 공통 literal/Git 조기 검사·실제 Gitleaks → 제품 deny 또는 무결정
PostToolUse → 제품 adapter → 공통 결과 검사 → 제품별 결과 은닉/중단 또는 무결정
Claude PostToolUseFailure → 같은 검사 → clean 실패 전달 / 발견·검사 오류 시 중단
Git 검사 호출자 → 명시 repo·policy의 index/outgoing 후보 → 같은 Gitleaks → pass 또는 exit2
Git hook renderer → 비활성 shell script 출력 → 격리 repo 이벤트 시험 / 운영 등록은 미실행
```

이는 작성한 source의 호출 관계다. native callback 관측이나 운영 등록을 뜻하지 않는다. 기존 원문 보호 hook은 다른 검사 목적이며 검사 결과를 서로 허용으로 덮어쓰지 않는다. 독립 동시 hook의 순서·출력 가공을 전제로 삼지 않는다.

## 유지·변경·제외

- 유지: 명시 Git 등록 범위, staged bytes·outgoing 전체 commit/메시지·tag, local-only 정책, 기본 Gitleaks 규칙, repo allowlist/환경변수에 의한 검사 해제 방지, 신뢰 scanner receipt, native 입력/완료 결과 검사, 오류와 발견 구분.
- 수정: 정상 checksum 전체 줄 형식과 중립 candidate 파일명의 AND 조건을 유지하며 LF/CRLF 및 여러 줄 경계를 처리한다. go.sum 파일 전체를 제외하지 않는다.
- 수정: literal Git 명령 경계를 보존하고 다른 명령의 옵션을 commit 옵션으로 취급하지 않는다. 파일 편집의 command처럼 보이는 문구는 실제 shell 실행으로 판단하지 않는다. shell 전체 해석·모든 동적 실행 차단이라고 주장하지 않는다.
- 추가: 스캐너의 발견 수와 소수의 검토된 고정 rule ID만 진단에 전달한다. 그 밖의 ID는 other-rule로 고정하고 File/Match/Secret/설명/응답 필드·원본 오류는 전달하지 않는다. metadata는 탐지 원문 대신 진단을 위한 것이며 정오탐 인증은 아니다.
- Sites: 기존 차단 응답의 원래 값·규칙이 없으므로 원인 해결 판정은 여전히 불가능하다. Sites 전체 허용이나 비밀 전달 예외는 추가하지 않는다. 합성 MCP 결과로 진단·은닉 계약을 시험한다.
- 제외: scanner 설치/업데이트, Git 등록 설치기·기존 hook 체인 적용, 제품 설치/trust/활성화·native 실험·운영 배포. 검사 CLI 작성과 운영 등록은 구분한다.

## 입력·실패·공유 경계

공통 scanner manifest는 secret-tools.toml이다. Native 연결은 기존 ~/.local/share/tr-kit/gitleaks/8.30.1 설치본의 archive/bin hash receipt를 확인하고 부재·오류 시 자동 설치하지 않는다. Git 명시 policy의 신뢰 scanner 경로와 native receipt 경로는 다른 입력 계약이며 자동 대체하지 않는다.

입력/결과8MiB, scanner subprocess35초와 Gitleaks 내부30초, 비활성 template45초 timeout을 유지한다. clean은 allow가 아닌 무결정이다. Pre 오류는 해당 실행 보류이며 Post는 이미 실행된 부작용·원본 transcript를 되돌리지 않는다. Codex는 고정 block reason, Claude는 지원되는 Bash/Read text/MCP 결과 schema에서만 교체하고 다른 계약은 중단한다. code-mode 중간 출력·백그라운드·다른 저장 hook의 원문 보호는 보장하지 않는다.

직접 코드·합성 payload 검증과 실제 제품의 등록·신뢰·callback·모델/화면 전달·활성 hook 조합은 구분한다. 이전 원문 보호151개 시험도 이 기능의 검증으로 재사용하지 않는다.

## 시험·감사 상태

scratch 구현·직접 반복 검수와 두 차례 정적 감사를 완료했다. 운영 적합/native 완료와 구분한다. 최종 source·직접 시험·실제 Gitleaks·정적 감사와 남은 native 범위는 [검증 요약](../verification.md)에 연결한다. 기존 자체 시험의 import/adapter/CLI 경로·안전 진단 기대를 변경한 근거와 초기 실패는 로컬 작업 기록에 보존한다.

### 추가 경계 보완

- Gitleaks8.30.1의 [location.go](https://github.com/gitleaks/gitleaks/blob/v8.30.1/detect/location.go) 37~50행은 이전 LF 위치를 시작으로 쓰며 53~72행의 마지막 개행 없는 경우에는 startLineIndex가 기본0으로 남는다. [detect.go](https://github.com/gitleaks/gitleaks/blob/v8.30.1/detect/detect.go) 446~480행은 해당 범위로 Line/currentLine을 만든다. 따라서 checksum 예외는 전달된 전체 블록의 모든 행이 정상 형식인지 검사한다. 원문 bytes를 정규화하거나 앞선 정상 행 하나로 오염된 뒤 행을 허용하지 않는다.
- shell LF 경계와 backslash-LF 연속을 구분한다. single quote의 실제 데이터는 보존하며 이는 제한적 literal parser다. 완전한 shell 문법·동적 source 해석기는 아니다.
- Claude Pre template는 onFailure:block을 사용한다. 해당 기능의 지원 버전(2.1.295+)과 native 실제 효과는 운영 연결 전에 별도 확인해야 한다. Codex 시작 실패를 제품이 어떻게 처리하는지도 source 실행 성공만으로 보장하지 않는다.

Git hook renderer는 명시 mode/source/repo/policy/Python 경로를 인용해 script를 stdout에 출력할 뿐 설치하지 않는다. 실제 pre-commit/pre-push 이벤트의 성공·차단과 index/로컬 bare remote 불변을 임시 저장소에서 검사한다. 운영 기존 hook 소유권·체인·등록 lifecycle은 여전히 미이관이다.

### 정적 감사 후 보완과 판정

- 입력 필수 식별자·known shell/Read 자료형을 검사하고, 누락/null/잘못된 command를 clean으로 취급하지 않는다. unknown tool은 JSON 입력 전체와 원 문자열을 검사하며 새로운 실행 권한을 부여하지 않는다.
- native scanner 후보는 전체 JSON 표현과 key/value 문자열의 원 bytes를 함께 포함한다. 개행·역슬래시를 복원 추정하는 방식이 아니다. 전체 JSON8MiB·최대65536구조노드로 제한하며 전체 후보 bytes는 그 표현과 원 문자열의 합이다. 여러 표현에서 같은 값이 탐지될 수 있으므로 진단 count를 서로 다른 비밀 개수로 해석하지 않는다.
- literal tokenizer가 인용 데이터와 실제 명령 구분자를 구분하도록 보완했다. Git 옵션 값·서명 key·env wrapper를 구분하고 간접 pathspec은 대상이 확정되지 않은 것으로 보류한다. `--message=fixture -an` 미탐이라는 지적은 기존 코드에서도 실제 차단돼 채택하지 않았다.
- 환경 출력에도 quote를 보존하는 continuation 처리를 적용했다. Pre에도 고정 안전 진단을 전달하고 Git CLI는 policy_violation/finding/unavailable을 구분한다. 비밀 원문·가변 경로는 반환하지 않는다.
- Git의 수집 총량·전체 이력 실행시간에는 native8MiB/scanner35초와 같은 전역 상한이 없다. 기존 repo별 Git 호출30초와 scanner35초를 전체 검사 상한으로 보고하지 않는다. 큰 이력의 메모리·디스크·전체 시간은 남은 성능/운영 검증 범위이며 이 구현의 새 보장으로 추가하지 않는다.

### 후속 감사의 최종 대조

- 주석 안의 heredoc 표식으로 실제 명령을 데이터처럼 제거하는 결함과 붙여 쓴 -t template 값 오탐을 보완했다. quoted # 파일명·정상 heredoc·주석 뒤 실제 위반·끝난 heredoc 이후 위반을 회귀한다. scanner 실패 Pre 시험은 정상 command로 scanner 단계에 도달시켜 확인한다.
- -S 분리 key 인수를 건너뛰라는 지적은 채택하지 않았다. [Git 공식 commit 문서](https://git-scm.com/docs/git-commit)의 -S는 key ID를 공백 없이 붙여 쓰도록 정의한다. 다음 -a는 서명 key로 삼으면 안 된다. 붙인 -Sabc는 보존하고 실제 -a는 계속 차단한다.
- [Codex Tool coverage](https://learn.chatgpt.com/docs/hooks#tool-coverage)는 write_stdin이 새 PreToolUse를 실행하지 않는 transport라고 명시한다. 따라서 chars를 검사하도록 함수를 추가하는 것만으로 인터랙티브 실행의 사전 차단을 보장할 수 없다. chars는 일반 프로그램의 입력일 수도 있어 shell 명령으로 일괄 해석하지 않는다. 이 제품 경계와 분할 입력·세션 식별은 후속 native/운영 검증 대상이다.
- functions.exec 같은 code-mode 완료 결과가 어떤 이름·schema의 native 이벤트로 전달되는지는 관측하지 않았다. 등록 matcher 밖의 새 도구까지 검사가 실행된다고 주장하지 않는다. 임의 matcher 확장·미확인 schema의 강제 교체로 해결됐다고 하지 않는다.
- 마지막 작은 보완 뒤 전체204개(시크릿53+원문 보호151)를 독립 프로세스3개에서 병렬 반복해 모두 통과했다. 동일 source 지문을 유지했다. 정적 감사가 이 마지막 작은 보완까지 다시 읽었다고 주장하지 않는다.
