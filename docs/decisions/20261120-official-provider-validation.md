# 1번: 공식 provider 격리 설치·직접 호출 검증

2026-11-20 사용자 “1번부터 ㄱㄱ”에 따라 기존 선택 버전을 새 검증 경로 `/data/projects/_scratch/tr-kit-official-validation-20261120`에 준비했다. 운영 plugin/config/trust·개인 데이터·기존 세션·원격 배포와 분리한다. 실제 제품 통합·전체 감사·운영 전환은 다음 단계다.

## 재사용과 실제 준비

- 공식 Skills CLI 1.9.0을 별도 npm prefix에 설치하고, 기존 고정 commit의 BMAD·Anthropic 문서/프런트엔드·Diagram Design·Android/Wear·Android testing·README skill을 프로젝트 범위의 Codex/Claude 위치에 설치했다. rename·원문 치환·자체 설치기 구현은 하지 않았다.
- Archify는 웹 배포 검색에서 한 skill을 확인하고, 기존 commit을 유지하기 위해 공식 system skill-installer의 명시 ref/dest로 설치했다. 글로벌 설치·최신 commit 자동 채택을 하지 않았다. 원문·203개 리소스를 검수하고 공식 doctor/demo를 실행했다.
- Wiki 1.0.0과 Claude-Mem15.2.1은 공식 Codex 관리자와 격리 Claude 관리자2.1.329로 설치했다. Claude 관리자는 별도 npm prefix에서만 사용했다. 공식 `install.cjs`의 플랫폼 선택 동작을 확인한 뒤 해당 lifecycle을 실행했으며, npm이 받은 native binary를 그 설치본의 launcher 자리에 배치하는 공식 설치 동작이다. kit이 외부 SKILL/절차를 치환한 것이 아니다.
- Claude Wiki native payload에는 별도 query entry가 없어, 기존 선언된 `wiki-query` 원문을 공식 skill-installer로 별도 프로젝트의 `.claude/skills`에 설치했다. 원문이 Claude/Codex 공통 query protocol임을 확인했다. 관리 workflow를 read-only query 대신 호출하지 않았다.
- 기존 own toolchain glue를 실제 실행해 Context7 0.8.2, Playwright CLI0.1.22/engine1.64.0-alpha-1790635538000/Python1.64.1·Chromium, Semgrep1.182.1, Trivy0.76.1을 새 prefix에 공식 npm/uv/release/browser 수단으로 준비했다. 호스트 PATH·shell startup·기존 receipt를 변경하지 않았다.

## 원문과 리소스 대조

요청한 skill은 제품별42개(metadata3개 포함)였고, 설치된41개씩의 원본 파일을 고정 commit archive와 대조해 일치를 확인했다. BMAD retrospective는 아래 오류로 두 제품 모두 설치되지 않았다. 호출용 registry에는 metadata를 제외하고 제품별46개 entry를 기록했다. 명시 설치 root·설치 근거·제품 계약 검수92개가 fresh 검사에 통과했다. 이 상태는 로컬 검수 기록과 현재 파일의 일치이며 공급망 서명·native 발동·모든 workflow 성공을 인증하지 않는다. npm 전이 의존/런타임의 적대적 변경 전체를 동결한 것으로도 확대하지 않는다.

공식 native payload도 manager가 취득한 고정 commit과 대조했다. Wiki Codex32/Claude54파일, Claude-Mem 각198파일이 그대로 일치했다. Python runtime이 만든 bytecode는 skill 원문 대조에서 별도 취급했으며 원문 수정으로 세지 않았다. 원문/runtime은 kit 배포 구성요소에 넣지 않는다.

## 실제 실행 결과

| 대상 | 실제 확인 | 남은 범위 |
| --- | --- | --- |
| 개발 도구 | 버전·Semgrep 합성 탐지/정상, Python/CLI 실제 Chromium 클릭·격리·캡처·자기 세션 종료 | 실제 사용자 프로젝트·원격 서비스 미실행 |
| Context7 | 공개 React18.2.0 library/정확 버전 원문 조회 | 사용자 자료·계정 연결 미실행 |
| Trivy | 실제 checks/CVE DB + 합성 IaC/취약 lockfile | 회사/개인 실자료 미전송 |
| BMAD | 공식 setup·설치 모듈 help·build workflow 렌더 | 전체 개발 workflow·모든 agent/model/native 검증 아님 |
| Archify | 공식 doctor와 standalone demo HTML 생성 | 사용자 구조도 생성·browser/finalize 전체 검증 아님 |
| Wiki | 공식 CLI/help·합성 hub session status, 새 Codex read-only query에서15분 근거 반환·fixture3파일 보존 | 실제 hub·수집/native hook 미실행 |
| Claude-Mem | 공식 worker·readiness·MCP initialize/19 tools·빈 합성 project 검색·소유 worker 종료. CLI 연결 보완 후 ready | 기존 DB·실제 대화 수집·AI observer 추론·사용자 인증·native 등록/도구 호출 미실행 |
| README | 새 Codex에서 원문 skill로 합성 repo README 작성, 실제 Node test/사용 예제 검사 | 실제 kit README 재작성 아님 |
| Diagram Design | 새 Codex에서 기본 스타일 합성 막대 HTML/SVG 생성, 공식 self_check/export 통과 | PNG/브라우저/Claude 모델 검증 아님 |
| doc-coauthoring | 새 Codex에서 Context Gathering만 실제 수행, 사실·가정·미결·질문 분리 | 문서 작성/독자 시험 전 과정 미실행 |
| Android architecture | 새 Codex에서 합성 모듈 경계·캐시 요구 검토 | Android/Wear SDK·API·빌드·기기 테스트 미실행 |
| Worktrunk / Orca | 기존 CLI 실제 버전 wt0.80.0 / Orca1.4.242 | worktree 이동·원격 세션/서버 변경 미실행 |

## 자체 연결 보완

실제 browser probe에서 Python 코드의 인용부호 손실을 발견해 raw string으로 교정하고 mock에서도 전달 코드의 compile을 확인하도록 보강했다. CLI의 file URL 제한을 끄지 않고 합성 HTML 하나만 응답하는 임시 loopback 서버를 사용한다. 긴 임시 경로의 Chromium socket 실패는 짧은 새 evidence 경로로 분리했다. 공식 CLI의 unique selector 계약으로 click을 실행한다. 실패한 기록과 자체 session/server 종료 근거를 보존했다.

격리 worker는 처음 Claude CLI 부재로 degraded였다. own schema2 binding에 선택 `claude_bin`을 추가해 공식 launcher의 실제 파일/bytes를 묶고 해당 디렉토리만 clean PATH에 넣었다. 다른 CLI를 Claude로 쓰거나 호스트 PATH/인증을 상속하지 않는다. 실행 의존 변경은 connection_id를 바꾸므로 새 시험 data/state를 사용했고, 기존 profile/marker를 덮어쓰지 않았다. 실제 ready와 정상 stop을 확인했다. 전체504개 시험과 관련 memory33개/toolchain26개 시험이 통과했다.

## 최초 미결과 재조립 보류

1. 고정 BMAD commit의 `bmad-retrospective/SKILL.md` description은 YAML 구문 오류다. 공식 설치기의 exit0과 실제 요청 목록 일치를 따로 확인해 누락을 발견했다. 원문을 수정하거나 다른 버전으로 자동 대체하지 않았다. 원문 module update URL도404라 최신 상태를 확인하지 못했다.
2. Python quoted heredoc의 `set(...)`을 환경 출력으로 오인하는 사례가 운영 hook과 새 source classifier에서 확인됐다. classifier에 합성 문자열만 전달했고 그 명령을 실행하지 않았다. 범용 Python 본문을 제외해 우회하거나 운영 hook을 꺼서 해결하지 않았다. 2번의 hook/native 통합 보완 대상으로 남긴다.
3. 기존 대조 catalog가 요구하는 Sites1.1.6 원문 파일이 없어 source fresh gate가 unavailable이다. 현재1.1.7은 다른 hash다. 실행 버전·가드 검사 범위를 임의 변경하지 않았고, 기존 catalog/pin/실패 결과를 보존했다. 새 대조 입력 선택을 사용자에게 확인 중이다. 새 source 묶음을 생성·검증하지 못했으므로 private common pin을 자동 갱신하거나 새 배포 후보를 완료로 표시하지 않는다.

검토 가능한 별도 catalog 초안은 로컬 `catalog-candidate-current-sites.local.json`이다. 기존46개 source 중45개는 유지하고 Sites 대조 경로/원문만 현재 공식1.1.7로 선택한 초안이다. 기존1.1.6 원문이 없어 전후 의미 비교는 미확인이다. 현재171줄 원문은 대조 자료로 읽었으며 실행/설치/게시 지침으로 발동하지 않았다. 초안은 **미채택**이고 fresh 조립을 통과시키는 입력으로 사용하지 않았다. 실행 provider의 버전도 바꾸지 않았다. 입력 채택과 실제 검증은 사용자 확인 뒤 별도 수행한다.

로컬 증거는 `_bmad-output/official-provider-validation-20261120/`에, 공식 설치본·도구/worker/browser 로그와 검수 기록은 위 별도 검증 경로에 있다. 실제 시험 worker는 종료했고, auth 복사·사용자 대화 수집·commit/push·운영 배포를 하지 않았다.

## 후속 승인: 공식 대조 입력 채택과 재조립

사용자가 “아 공식 원문으로 해줘 ㅇㅇㅇ 공식기준이야”라고 확인해 위 초안을 채택했다. `catalog-adopted-official.local.json`은 현재 공식 Sites1.1.7 원문과 기존45개 source identity를 검사한다. 이전 common catalog는 구 schema1, 현재 검사기는 schema2였으므로 형식도 현재 make_catalog로 생성했다. 검사기 구현·승인 정책·원문 보호 기준을 바꿔 통과시킨 것이 아니다. 이전 catalog와 원문 hash·실패 기록은 보존했고, 과거1.1.6 원문과의 의미 비교는 계속 미확인이다.

공통 Codex/Claude150파일 source 묶음을 fresh source/전송·원문 보호·비밀 검사로 재조립했다. 명시 provider 입력은 앞서 실제 설치·검수한 제품별46개 registry다. 예전5-entry 선언의 소실된 Sites 실행 경로로 대체 실행하지 않았고, Sites 실행 버전의 업그레이드나 게시도 하지 않았다. 전체53개 own skill의 운영 준비 완료를 뜻하지 않는다.

G7 기준 공통 묶음과 비교한 변경은 references/claude-mem.md·toolchain.md와 scripts/claude_mem.py·toolchain_verify.py의4개이며 추가/삭제는 없다. 앞서 전체504개·관련33/26개로 검수한 선택 Claude CLI 연결과 실제 browser probe 보완이다. 이 변경 목록과 실제 새 파일 명세를 대조해 private의 공통 exact pin을 갱신했다. 기존 인터페이스/skill allowlist·추가 파일 거부·역할 정책은 유지한다.

private의46개 원문 identity도 동일했으므로 승인된 공통 catalog를 재사용해 제품별48파일 source 묶음을 fresh 조립했다. 공통 구현이나 catalog 완성 사본을 private에 복사하지 않았다. 결과 source는 `/data/projects/_scratch/tr-kit-validated-source-{codex,claude}-20261120`, private는 `/data/projects/_scratch/tr-kit-validated-private-source-{codex,claude}-20261120`이다. 이는 source 묶음이며 native 설치·hook trust·운영 배포는 수행하지 않았다. 재조립 보류는 해소됐고 BMAD 원문/update 문제·Python heredoc 오탐·양 제품 전체 native 검증은 남아 있다.
