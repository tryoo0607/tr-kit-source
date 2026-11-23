# 전체 기능 이관 현황과 후속 순서

## 현재 후속 순서 — 2026-11-23

이 목록이 지금 진행 중인 감사 후속 순서다. 아래 과거 이관표·권장 순서는 그 당시 계획과 관측을 보존한 이력이며 실행 대기 목록으로 중복 적용하지 않는다.

| 순서 | 상태·근거 | 남은 범위 |
| --- | --- | --- |
|1 형식 전달 | A-02의 private2곳 교정·한정 검증. 개인 native-format-routing 기록 | 새 묶음 연결·native 수집 검증은5번과 별도 활성화 범위 |
|2 캐시 | A-01의2개 보존/정리·원래 source 검사 완료. [감사 후속 기록](decisions/20261120-whole-kit-audit.md) | 미래 재생성 방지 보장 아님 |
|3 보고·승인 | [보완·실제 모델 시험](decisions/20261120-reporting-approval-validation.md) 수행 | Claude 분량 초과·기존 운영 hook 분류 차단과 제한된 시험 범위를 미결로 유지 |
|4 문서·목차 | [현재/이력 교정과 백업 절 순서](decisions/20261123-status-docs-and-backup-order.md) | 상세 검수·비대상은 기록 참조. 다른 발견을 해결로 변경하지 않음 |
|5 후보 통합 | [새 후보 검증 완료](decisions/20261123-candidate-pin-native-validation.md) | exact pin4개 정렬·새 묶음8개·전체 회귀·양 제품 native 연결/경계·제거 확인. 남은 실제 모델/실자료·운영 한계는 유지 |
|6 운영 적용 | 아직 진행하지 않음 | 승인한 대상/범위에서 commit·전송/설치·신뢰·새 세션 검증. 실제 배포 요청과 호스트 가드/제품 권한을 독립 확인 |

현재 후보의 source/native exact pin은5번에서 정렬·격리 검증했다. 운영 version/manifest가 달라지면 관련 pin·private 묶음을 재대조하며 전체 운영 적합은 아직 판정하지 않는다. 운영 자료/DB·백업 timer·Wiki 수집을 자동 활성화하지 않는다. PTBMAF·Design Doc·Obsidian·NotebookLM, README 전면 재작성·kit 안내 artifact는 아래 사용자 후속 구상에 보존하며 이번4번에서 도입하지 않는다.

## 이관·후속 이력 — 각 시점의 기록

초기 source 수치·미이관/미검증·실패와 당시 권장안을 보존한다. ‘현재 후속’ 대신 기록 시점을 표시하며 최신 판단은 위 목록과 검증 현황을 따른다.

### 2026-11-20 후속 당시: 3번 보고·승인 대응 보완과 제한 검증 완료

[3번 기록](decisions/20261120-reporting-approval-validation.md)에 공통2파일 보강·516개 회귀·양 제품 최종 사례와 남은 분량 위반을 남겼다. A-03 전체 해소는 보류하고 초기/중간 실패를 유지한다. 다음4번은 A-04/A-05 현재/과거 문서와 개인 백업 목차 교정,5번은 변경 반영 후 제품 패키징·private exact pin 정렬·연결/영향 검증,6번은 승인 범위의 운영 적용이다. 이번에는 운영 설치/배포·pin/역할 변경을 하지 않았다. 아래 항목은 각 시점의 이력이다.

### 2026-11-20 후속 당시: 1번 형식 전달 source 교정·2번 캐시 정리 완료

A-02는 개인 scratch의 native-format-routing 기록에 source 수정·118개 회귀와 직접/모델 관측을 남겼다. 이후 별도 승인한 A-01 캐시2개를 보존·제거하고 원래 공통 source의516개 회귀·양 제품 source 조립과 기존 pin 일치를 확인했다. 현재 근거는 [verification.md](verification.md)다. 다음에는 A-03 모델 보고 대응, A-04/A-05 기록·목차 교정과 변경 반영 후 제품별 재검증·설치/배포가 남는다. 이번 정리는 운영 적용이 아니며 아래 목록은 각 시점의 이력이다.

### 2026-11-20 후속 당시: 전체 감사 완료·발견 사항 보완 필요

[전체 감사](decisions/20261120-whole-kit-audit.md)에서 native common 형식 전달이 빠진 개인 호출2곳을 재현했다. 원래 공통 source의 bytecode2개도 조립을 막는다. 이를 보존한 별도 검사용 사본의516개/private115개 회귀와 양 제품 패키지4개 조립은 통과했다. Claude 보고 오류·기록의 현재/과거 혼재·개인 백업 목차 차이도 남아 있다. 감사만 수행했고 자동 수정·운영 전환은 하지 않았다. 다음 보완 묶음과 미실행 범위는 감사 기록을 따른다.

### 2026-11-20 후속 당시: 합성 대표 업무·실제 수동 압축/재개 시험 완료

[실제 모델 시험 기록](decisions/20261120-real-work-compaction-validation.md)에 양 제품의 분석·승인된 최소 수정·고정 테스트·위치 참조와 native 수동 압축·동일 대화 재개 결과를 남겼다. 운영 설치/배포는 하지 않았다. Claude의 미확인 설명·과도한 재확인은 발견 사항으로 유지하며, 자동/반복 장기 압축·항상 합의 재읽기·전체 기능 성공은 입증하지 않았다. 다음은 이 발견과 기존 미결을 포함한 전체 kit 감사 범위의 검토이며, 새 구현/운영 적용 승인을 뜻하지 않는다. 아래 후속 순서는 해당 이력 당시 상태다.

### 2026-11-20 후속 당시: Claude-Mem native MCP 격리 검증 완료

[MCP 검증 기록](decisions/20261120-native-mcp-validation.md)에 양 제품의 native19개 도구·빈 DB 조회·자동 미기동·명시 worker 수명 관리·잘못된 binding 거부와 정리를 남겼다. Python/Chroma 전제를 시험 경로에 준비한 결과이며 운영 설정이나 kit 구현을 변경하지 않았다. 실제 모델 선택·자료 업무·자연 발동·압축/재개와 운영 전 전체 감사·배포는 남는다.

### 2026-11-20 후속 당시: private 패키징·설치본 연결 검증 완료

[native 연결 기록](decisions/20261120-native-private-interface.md)에 공통 source/native 별도 pin, 실제 private 패키징·설치/발견·초기 지침·제품별 실패 처리·제거/공통 보존을 정리했다. 운영 배포는 별도다. 남은 통합 항목은 선택 MCP의 native 등록·연결, 실제 모델 업무/자연 발동·압축/재개 및 운영 적용 전 전체 감사다.

추가로 실제 Claude 새 세션의 정상/공통 부재 응답을 각1회 확인했다. 실패 때 확인 요청·private 작업 보류 의사를 관측했으며, 도구 미노출 시험이므로 실제 실행 보류·전체 업무 검증과 구분한다. 근거 없는 원인 추정·장황함은 별도 미교정 발견으로 남겼다. 다음 통합 대상은 선택 MCP의 native 등록·연결이다.

### 2026-11-20 앞선 후속 이력

아래11월18일 목록과 초기 후속은 이력이다. [현재 검증 기록](decisions/20261120-hook-bmad-native-validation.md)에서 Python hook 오탐 보완, 승인한 공식 BMAD 수정본·retrospective 복구, 공통 native 설치/갱신과 양 제품30개 callback 사례를 확인했다. 공통150파일 source/154파일 native, private48파일 source와 새 common exact pin 검수를 마쳤다.

다음 연결 과제는 **private의 raw common 계약을 유지하면서 native 설치본도 검증해 연결하는 방법과 private 패키징**이다. source 묶음을 native 설치본으로 간주하거나 exact pin을 완화해 해결하지 않았다. 실제 모델·압축/재개·MCP/실자료·운영 배포까지 완료한 상태가 아니다.

기준일: 2026-11-18. 기존 common/private source와 새 scratch 작성본의 기능·지원 자료·제품 선언을 대조한 보고다. 이 문서는 상태·차이·후속을 연결하며 각 기능의 기준 본문이나 작업 정본을 대신하지 않는다. 최초 목록 조사에서는 실행 코드를 수정하지 않았고, 이후 승인된 G1~G6 source 구현 상태를 아래에 갱신했다. 운영 역할 정책·설치본은 변경하지 않았다.

### 조사 범위와 판정

- 기존 공통 source134파일·private60파일, 합계194파일의 책임을 분류했다. common/adapters/scripts/tests·공통 CI·명시 저장소 안내/metadata가 범위다. 소스 본문과 dependency 선언의 외부 ID, 제품별 MCP/관리 연결, 설치/배포·검증 도구를 포함한다.
- cache/out·외부 설치본·profile/인증·개인 자료·실서비스 상태는 조사하지 않았다. 단순 파일 집계는 의미/행동 보존의 증명이 아니므로 변경 기록·실제 코드·검증 범위를 함께 대조했다.
- 새 common53개·private9개 자체 skill과 지원 파일이 있다. 최초 목록 대조 당시 직전 검증 source manifest와의 실행/skill/adapter/test 파일 변경은0개였다. 이후 G1 변경·시험은 [G1 기록](decisions/20261118-g1-git-enrollment.md)과 verification.md에서 따로 추적한다. 이전 직접/모델 시험을 이번 새 시험으로 합산하지 않는다.
- `source 작성`은 연결 지침/코드가 있다는 뜻이다. `미이관/미구현`은 기능이나 연결이 더 필요하다는 뜻이고, `미검증`은 수행·효과를 관측하지 않았다는 뜻이다. 배포는 별도 상태다.
- 아래 `권장`은 후속 구현/채택 방향이다. 이번 조사로 새 기능 제외·설치·업데이트·배포를 승인하거나 실행한 것이 아니다. 외부 원문 동봉/사본 변형을 가져오지 않는 원칙은 이미 확정된 기준이다.

### 1. Source가 작성된 기능

| 기능 묶음 | 현재 담당/지원 자료 | 실제 확인과 한계 |
| --- | --- | --- |
| 공통 원칙·요구/승인 연결 | instructions/workflow | 자체 지침 작성. 초기 주입·압축/재개와 기계적 강제는 별도 |
| 작성/수정·개별/전체 감사 | plugin-authoring·대상별6개/공통3개 reference | 작성/검수 구조 재구성. 모든 kit 전체 적합 판정은 아님 |
| BMAD28개 진입점 | bmad/bmad-* 자체 연결·connection | 공식 workflow 입력/결과 연결 작성. 공식 본문·모듈 resources 실행은 미검증 |
| 기술문서·개발 UI·브라우저 | find-docs/frontend-design/playwright-cli | 선택한 공식 CLI/skill 연결. 도구 준비·브라우저/resources·실제 요청 검증은 후속 |
| 문서 공동작성·README | doc-coauthoring/github-readme-generator | 업무 owner·조건/입력 연결 작성. 공식 workflow와 개별 사용 조건 검토 필요 |
| 구조/업무 시각화·게시 | archify/diagram-design/artifact-publish·양 제품 게시 reference | 계정/범위·payload 검사 작성. 실제 게시·접근/렌더·제품 UI는 미검증 |
| 원본·작업기록·경험·Wiki | document/mem-search/wiki·assets.py·제품 Wiki reference | 로컬 원본/출처/검색 helper·공식 연결 작성. 실제 Docling/QMD·MCP/worker·Wiki 실행은 후속 |
| 설정·프로젝트 | profile-setup/project·profile_config.py·git-excludes.py | 필드/문법 validator·원본 경로 소비·전역 제외/백업 예외 작성. 전체 resolver/sync 실행기는 없음 |
| 세션·Orca·worktree | session/orca-cli/orca-update/worktrunk·runtime_refresh.py | 기존 공간/위임/갱신 판단·helper 이관. 실제 native session 조작·소비 확인은 미검증 |
| 원문 보호·비밀/커밋/전송 검사 | upstream_guard/artifacts·secret_guard·CLI/비활성 renderer·security-scan | 직접/합성 검사·source 조립 gate 및 G1 명시 등록/chain/복귀 작성. 실제 운영 등록·제품 native 효과는 미검증 |
| Android/Wear6개 | 전문 wrapper·android-work | 역할/범위·버전/기기·결과 연결 작성. 앱 빌드/SDK/API·기기/공식 workflow 미검증 |
| 개인 홈랩6개 | homelab/config/architecture/audit/record/recovery | 역할·의도/source/관측/기록·송수신자 경계 보존. 실제 인프라·전달/회신 미실행 |
| 개인 BMAD 백업 | artifact-backup·실행/설치기 | 임시 Git/bare remote·기기/발견·검사·9파일 설치/복귀 검증. 실제 timer/원격 저장소/복원과 구 설치 전환은 후속 |
| 개인 자료실·REA·Wiki 수집 | personal-library·private-setup의 선택 REA/capture reference | disabled/admission·fake runtime/helper/protocol 시험. 실제 서비스·공식 runtime/helper·수집 미검증 |

세부 근거는 각 이관 결정과 [공통 검증](verification.md), 별도 private source의 docs/verification.md에 있다. private 구현/검증 상세 정본은 여기 복제하지 않는다.

### 2. 이름이 달라지거나 자체 진입점에서 빠진7개 ID

기존 공통 자체 SKILL과 제품 dependency ID의 합집합은59개다. 여기에는 모듈 metadata도 포함돼 있어 새 자체 skill53개와 기능 수로 직접 비교하지 않는다. 단순 이름 차이는 아래7개이며 새 이름은 plugin-authoring이다.

| 구 ID | 처리/현재 연결 | 아직 확인할 것 |
| --- | --- | --- |
| skill-authoring | 합의한 plugin-authoring의 skill/hook/kit 저작·감사로 재구성 | 별도 정적 읽기량 측정기도 G3에서 source 이관·검수. native 적용/모델 전체 읽기는 별개 |
| skill-creator | 원문을 동봉하지 않고 실제 공식 저작 기능을 선택 | 제품별 공식 설치/실제 식별자·이전 namespace 호환성 |
| bmod-core-tools/bmod-method/bmod-toolsmith | 공식 BMAD 설치가 관리하는 모듈 metadata. 자체 업무 skill로 복사하지 않음 | 공식 설치의 필수 metadata/resources 충족 |
| wiki-manager | 공통 wiki의 Claude adapter가 공식 관리 provider를 선택 | 실제 공식 설치·제품 식별자/이전 이름 사용 호환성 |
| wiki-query | 공통 wiki가 읽기 전용 공식 provider를 선택 | 실제 설치/호출. 관리 명령 fallback이나 자체 복제는 하지 않음 |

없어진 이름을 모두 기능 삭제로 분류하지 않았으며, 이름 연결만으로 실제 공식 동작 완료도 인정하지 않았다. G5에서 자체 common의 native 포장을 추가했으나 외부 공식 provider 설치/resources·native 호출은 G7 검증 대상이다.

### 3. 구현·연결 상태와 남은 작업

| ID | 확인한 빈자리 | 권장 처리·재사용 범위 | 완료 확인에 필요한 것 |
| --- | --- | --- | --- |
| G1 | source 구현·임시 Git 직접 검수 완료. 명시 plan/apply·chain·status/rollback 및 engine 예외 범위 강제 추가 | 기존 자체 snapshot/보존·복귀 개념과 새 검사 CLI 재사용. 공식 scanner를 외부 receipt/pin/hash로 연결하며 복제하지 않음 | G1 전용24개 및 관련 실제 scanner6개 통과. 운영 등록·실제 제품 native 조합은 후속. 상세 실패/보완·한계는 verification.md |
| G2 | source 구현·격리 protocol 검수 완료. setup_dev_tools/setup_git_guard/verify_dev_tools와 공통 준비/검증 helper 추가 | 공식 npm/uv/release·Chromium installer 연결. 새 prefix·pin/버전/receipt·부분 실패 보존과 새 prefix 회복 절차. 외부 runtime 동봉 없음 | 실제 공식 패키지/브라우저 취득·실환경 semantic probe는 미실행. 격리 시험과 새 source 사용·조립 검증은 verification.md |
| G3 | source 이관·직접/새 세션 검수 완료. context_check와 새 source cases·reading-flow 연결 작성 | 기존 full SKILL/절·metadata·비증가 비교를 보존하고 measure-only·canonical 부분 겹침·명시 source/flat scope 추가. 외부 원문 동봉 없음 | 전용26개·관련 조립 포함52개 통과. 실제 source5경로 측정과 비교 미통과/입력 오류 구분. token·자연 발동·Claude/압축은 미실행 |
| G4 | 15.2.1 공식 entry 연결·worker 수명/health·양 제품 설정 출력 source 작성. native 등록은 미실행 | 명시 provider/runtime·data/state/port, no-autostart·새 manual profile. 공식 stdio 직접 exec, 소유 process/health/readiness 검증. 엔진 동봉 없음 | 합성 process/MCP 및 새 Codex 사용 검수는 verification.md. 공식 설치본/resources·기존 DB 연결·제품 native 조합은 G5/G7에 남김 |
| G5 | 공통 양 제품 native 포장·현재 package/전송 후보 검사·격리 공식 CLI lifecycle·검사 전용 CI source 작성 | 경로/원문 보존·기존 assembler/guard renderer·공식 manager 재사용. 정적 plan과 apply 전 scanner 분리, partial 보존·이전 package 복귀. 기존 운영 설치·trust/push 변경 없음 | 중간 전체475개·최종 전용24개 통과. 양 제품151파일 native 후보, Codex0.167.2 실제 격리4단계·cache byte/제거 대조, source147파일 조립. Claude manager·native hook 신뢰/동작·private 통합/공식 provider는 미검증. verification.md 참조 |
| G6 | private에 명시 구3→신9파일 전환/보존·실패/복귀 source와 조건부 skill 연결 작성 | 기존 installer 생성/쓰기·공유 lock·실제 역할/기기/pin·비활성/job/backup lock 검사. 일반 legacy 거부·timer bytes/enablement·설정/자료 보존. 자동 stop/start·활성화·실제 백업 없음 | private 전체102개·전용30개 포함 통과. 양 제품 source48파일 fresh 검사, 동일 제약 새 Codex plan 성공. systemd는 fixture이며 실제 timer/host ABI·운영 자료/remote·복원·새 common/native private 통합은 미실행. private docs/verification.md 참조 |
| G7 | source 보완·격리 검수 완료. 설치 명세/근거·제품 검수·업데이트 차이 CLI와 memory/private 실행 전 검사 연결 | 공식 manager/기존 resolver 재사용. 검수 자체는 설치/인증/실행 증명이 아님. source pin120→150 검토 갱신·private 전체106개·양 제품 source 조립. 실제 npm package10/16파일 공식 archive 일치 | 공통 전체500개 후 최종 memory30/provider29개 통과·새 Codex2사례·양 제품4 native 후보. 공식 provider 전부 설치/필수 외부 closure·실제 workflow·native private·Claude/압축은 미실행. provider-status.md/verification.md 참조 |

G2는 새 기기의 도구 준비, G4/G7은 업무 실행 의존, G5는 제품 설치/배포 연결이다. 기존 설치본 실행이나 mock protocol 통과를 새 환경의 실제 준비/동작 성공으로 확대하지 않는다. 2026-11-18 G2에서 실제 세 pin 파일을 개별 대조한 결과 Gitleaks 중복은 없었고 secret-tools.toml에만 있었다. 최초 목록의 “security-tools에도 중복” 설명은 잘못된 정적 판독이어서 정정했다. 중복을 제거했다는 코드 변경/실적으로 세지 않는다.

기존 `.github/workflows/build.yml`에는 main push의 배포 분기가 있다. 새 source를 기존 저장소에 반영할 때 source push·격리 검증·운영 delivery가 어떻게 분리되는지 G5에서 먼저 확인해야 한다. 이번에는 push/CI 실행을 하지 않았고 실제 deploy key/활성 상태를 조회하지 않았다. source 작성 세션의 필수 기준 진입과 제품 초기 AGENTS/CLAUDE 주입도 G5의 연결/검증 대상이며 template 존재로 자동 로드를 인정하지 않는다.

#### records 런처7개 동작의 구분

| 구 동작 | 현재 판단 |
| --- | --- |
| doctor | bundled 파일 목록 확인 방식은 가져오지 않음. provider pin 확인과 공식 기능별 health는 다른 검사여서 실제 health/준비 연결은 G4/G7에 남음 |
| bmad-setup/bmad-render | 공식 BMAD setup/render로 업무 연결 대체. 별도 구 CLI 이름/launcher는 이관하지 않음. 실제 공식 수행은 미검증 |
| wiki/wiki-session | 공식 Wiki 관리/query/선택 helper 경로로 대체. 자동 개인 capture만 private admission이 소유. 수동 session/knowledge 작업과 자동 수집을 혼동하지 않음 |
| mem-mcp/mem-worker | G4의 전용 claude-mem.py와 공식 외부 entry로 대체. 자체 연결·수명/health source와 합성 검수 완료. 실제 공식 설치본 실행·native 등록·기존 DB 연결은 미실행 |

`records.py 전체가 없다`와 `모든 기록 업무가 사라졌다`는 같은 판단이 아니다. 반대로 업무 wrapper가 있다는 이유로 MCP·daemon 직접 기능까지 이관됐다고 하지 않는다.

### 4. 이관 목록에서 분리할 것

| 항목 | 처리 근거/현재 상태 |
| --- | --- |
| 외부 본문/runtime/resources 동봉·binding 치환 | 이미 합의한 금지에 따라 새 kit에 가져오지 않는 형식. 해당 업무는 공식 기능으로 연결 |
| 구 vendor 조립용 source fetch 경로 | 새 실행 공급자 설치와 분리. 외부 원문 비교에 필요한 취득/pin/차이 검토는 유지할 수 있으나 checkout을 실행 provider로 쓰지 않음 |
| 구 validator의 임시 변환 view | 공식 validator·명시 호환성 확인을 우선. 검사 통과를 위해 foreign 원문/사본 또는 미지원 필드를 조용히 바꾸는 경로를 가져오지 않음 |
| PTBMAF·Design Doc·방법론 목록/선택 | 기존 README/AUDIT도 미구현으로 기록. 기존 기능을 잃은 것으로 세지 않고 사용자가 원한 신규 계획으로 보존. 이번 목록 조사에서 구현하지 않음 |
| 전체 profile resolver/일반 문서 자동 sync | 필드/문법 validator와 일부 소비자는 있음. 실제 경로 충돌/Git boundary·remote·전송의 자동화는 없음. 기존에도 독립 sync 실행기는 확인되지 않았으므로 기존 기능 복구로 확대하지 않음. 필요한 소비자 검증·수동 절차와 새 자동화 요구를 분리 |
| Obsidian | 과거 스킵에서 2026-11-18 다시 활용 예정으로 변경. 아래 후속 도입 구상에 용도 보존. 기존 기능의 미이관이나 현재 필수 의존으로 세지 않음 |
| README 전면 재작성·kit 안내 artifact | 사용자 후속 순서에 남김. 별개로 배포에 필요한 최소 설치/복귀·자체 LICENSE/NOTICE/보안·버전/provenance 안내는 G5에서 검토해야 함 |
| .github 안내/의존 업데이트·UI metadata 등 | 구 저장소 관리 파일을 기능으로 세지 않음. CI·제품 표시 metadata 중 필요한 것은 G5, 안내 문서는 후속 문서 단계에 연결 |

#### 후속 도입 구상 — 2026-11-18 사용자 요청

- PTBMAF·Design Doc·방법론 목록/선택: 도입·구현할 후속 대상으로 유지한다. 앞서 논의한 분석과 설계 산출물 연결이 목적이며 이번 G1 구현에는 포함하지 않는다.
- Obsidian: GitHub를 통해 에이전트가 작성한 내용을 Linux·Windows·Android 등에서 열람할 예정. vault 위치·내용·저장소 공개/비공개·동기화와 충돌 처리·공통/private 배치는 아직 정하지 않았다. GitHub에 자료를 전송하거나 앱·플러그인을 설치하는 승인은 아니다.
- NotebookLM CLI: 오픈소스 CLI를 논문 분석 엔진으로 활용하는 안을 고려 중이다. 사용자가 기억한 후보명은 `notebooklm-py`이며 정확한 저장소·star·지원 기능·인증/사용 조건은 미확인이다. 자료관리 도구로 자동 분류하거나 논문/회사 자료를 업로드하지 않는다. 도입 검토 시 실제 후보와 자료 범위를 먼저 확인한다.

### 5. 구현과 별도로 남은 검증

- 새 공통/private의 실제 초기 주입·공식 skill/MCP 호출·제품 event/schema·입출력 교체·신뢰 승인과 전체 hook 조합.
- 문구만으로 포괄 차단됐다고 하지 않고 실제 source/원문 보호·시크릿·Git·host role·사용자 승인 각각의 보장 범위와 빈자리 대조.
- 설치본 heredoc 오탐 후보의 정확한 입력을 새 검사기에 대조. 현재 source에는 인용된 cat heredoc 회귀 사례가 있으나 기록한 Python heredoc 사례 전체를 재현한 근거는 미확인이다. 조사 단계에서 해결됐다고 바꾸지 않음.
- 기존 go.sum·게시/credential 경로의 정오탐과 product별 actual upload/계정 접근·render. 직접 검사 통과와 실제 게시 성공을 분리.
- 새 세션 명시 호출·자연 발동·실제 압축/재개·소유 호스트에서의 조율/수신/거부/회신·부재/부분 실패/복귀.
- 기존 모델 결과의 필요 이상 읽기·보고 누락·명시 설정 조회 시도와 보완을 보존하고 G3 측정/실제 관측과 연결. 반복 통과를 모든 요청의 강제로 확대하지 않음.
- 전체 요구 원문/정정까지 확정하는 감사와 이번 source 기능 대조를 구분. 초기 requirements의 draft/미검증 표시는 각 증거/합의에 따라 별도 정리해야 하며 파일 존재로 확정 합의로 올리지 않음.

현재 설치본·호스트별 활성 상태는 이번에 조회하지 않았다. 실제 자료 이동/백업/capture/NAS·설치·원격 전송/배포는 미실행이다.

### 6. 권장 후속 순서

2026-11-20 후속1번은 공식 설치·원문/리소스 대조와 실제 direct/Codex probe를 진행했다. [결과](decisions/20261120-official-provider-validation.md): own 전체504개 통과, 공개 도구/브라우저·BMAD 렌더·memory ready/stop·대표5 skill 호출 확인. 후속 승인으로 공식 Sites1.1.7 원문 catalog를 채택해 공통150/private48파일씩 재조립·private common pin을 갱신했다. BMAD retrospective 원문 오류·update404와 Python heredoc set 오탐은 남아 있다. 다음2번 제품 통합의 전체 통과로 세지 않는다.

1. G1~G4 source 구현·검수는 각각의 관측 범위에서 진행했다. G2의 실제 공식 취득/실행, G3의 실제 전체 모델 읽기/비용, G4의 공식 memory runtime/native 연결은 source 시험으로 완료 처리하지 않는다.
2. G7 source에 공식 설치 근거/리소스·제품 검수와 업데이트 차이를 연결하고 현재 지원/미결 표를 작성했다. 이후 실제 공식 provider의 격리 설치·필수 외부 closure·G4 ABI/기존 데이터 전환 검증이 필요하다. 기존 no-autostart·원문 무변형·자료 경계를 유지한다.
3. G5의 공통 native 양 제품 패키지·격리 lifecycle·검사 전용 CI/delivery source와 Codex 격리 manager 시험은 작성·검수했다. Claude manager·실제 hook trust/callback·공통+private 통합과 운영 전송/적용은 아직 완료하지 않았다.
4. G6 구 설치 전환·보존/복귀 source와 격리 검수는 완료했다. G7에서 새150파일 common source와 private 연계/회귀를 검수했다. 실제 기기의 상태·설정·job·timer 및 보존 경로·native private 연결을 확인한 뒤 공통 단독/공통+private·Codex/Claude native 통합과 실제 전환을 별도 진행한다. 실제 상태 변경은 해당 범위가 승인된 단계에서만 한다.
5. 미해결·미지원과 실제 검증 결과를 전체 감사로 정리한 뒤 운영 전환을 진행한다. 일반 문서 자동화·방법론 신규 도입·README 전체 재작성은 별도 계획으로 보존한다.

이 순서는 의존 관계를 정리한 권장안이다. G1~G7은 각각 후속 요청에 따라 기록한 source 구현·검수를 진행했다. 이를 운영 적용·공식 provider 일괄 설치/수집의 포괄 승인으로 확대하지 않는다. private common source pin은 G7에서 검토해 갱신했고 native 통합과 실제 공식 workflow 검증은 후속에 남아 있다.
