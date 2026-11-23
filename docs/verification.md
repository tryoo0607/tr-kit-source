# 검증 상태

## 현재 판정 — 2026-11-23

이 절은 기존 관측과 후속 구현·운영 적용의 현재 요약이다. 상세 수치·실패·제품/설정·revision별 한계는 해당 결정 기록이 소유한다. 아래 이력은 당시 결과이며, 그 안의 ‘현재’·‘최신’·‘미실행’을 최신 후보 상태로 읽지 않는다. **전체 운영 적합 판정은 계속 보류한다.**

| 대상 | 확인한 범위·시점 | 현재 남은 범위 |
| --- | --- | --- |
| R-52 재시작 배치 | [배포 전 검수](#재시작-배치-배포-전-검수--2026-11-23): durable 배치·수동 목록, Codex0.171.0 helper restart/restore·Claude2.1.330 helper cold restore·새 모델 prepare/list, 최종 공통600/private129개·8묶음·pin4개 통과 | Claude 즉시 restart는 수동. 실제 reboot/운영 rollout·새 묶음의 소비 증거는 미실행 또는 미확인 |
| 공통·private 구조 | 공통53/private9 자체 skill과 양 제품 adapter. [전체 감사](decisions/20261120-whole-kit-audit.md)에서 관계·기초 형식·연결 대조 | 전62개 모든 분기의 의미/실제 업무·원문 요구 전체 대조가 완료된 것은 아님 |
| A-01 캐시 | 11월20일2개를 외부 보존 후 제거. 원래 공통 source516개 회귀·양 제품 source 조립 | 미래 재생성 방지 보장 아님. 이번 검수는 source의 새 pyc 유무 확인 |
| A-02 형식 전달 | 기존 교정과 후속5번 새 묶음·118개 회귀, 설치된 private의 doctor/document10쌍 확인 | 실제 helper/capture 실행과 실자료 수집·운영 적용은 별도 |
| A-03 보고·승인 | [보완 지침](decisions/20261120-reporting-approval-validation.md)의 실제 모델 시험과5번 native 초기 전달을 구분 | Claude 분량 위반1건·기존 운영 hook 차단 유지. 새 실제 모델 비교·자연 발동/압축·전체 행동 해결 미확인 |
| A-04/A-05 문서·목차 | [4번 교정](decisions/20261123-status-docs-and-backup-order.md): 현재/당시 기록 구분과 백업 본문/reference의 절 순서만 정렬 | 문서 정리로 앞선 실패·미검증이나 kit 전체 적합을 해소하지 않음 |
| 공식 연결·native |11월20일 [공식/BMAD·hook](decisions/20261120-hook-bmad-native-validation.md), [private 설치/제거](decisions/20261120-native-private-interface.md), [MCP](decisions/20261120-native-mcp-validation.md)를 각각 격리 검증 | 대상 revision/제품/합성 또는 실제 실행 조건의 제한 유지. 현재 후보 전체의 성공으로 재사용하지 않음 |
| 대표 모델·압축 | [이전 묶음의 실제 대표 업무·수동 압축/재개](decisions/20261120-real-work-compaction-validation.md) | 자동 임계치·반복 장기 압축·매 재개 정본 재독·전 skill/실자료 보장은 아님 |
| 현재 후보 계약·운영 | [5번 검증](decisions/20261123-candidate-pin-native-validation.md): 새source/native8개 조립·pin4개 정렬·공통516/private118개 회귀·native34사례·양 제품53/62개 실제 노출·공식 entry/resource47개씩 대조 | 시험 버전과 운영 버전 구분.[6번 운영 적용](decisions/20261123-host-runtime-connection.md#운영-적용-결과--2026-11-23): 세 호스트 native 설치·공식 provider47개 연결·Codex 개별 trust·새 지침 전달 확인. dev01/Claude 명령 성공, nas-vm 명령은 sandbox loopback 오류로 미실행. 전체 운영 적합은 보류 |

4번 문서 검수는 전체 회귀가 아니며, 5번516/118개와 6번 공통525/private129개를 각 변경 후보에 실제 재실행했다. BMAD 자동 갱신404 미지원, 실제 개인 자료/NAS/기존 DB·timer·capture·운영 복구와 후속 신규 도입은 각 원래 범위에 남긴다. [현재 후속 순서](migration-status.md#현재-후속-순서--2026-11-23)를 따른다.

## 재시작 배치 배포 전 검수 — 2026-11-23

기준 revision은 `55c4498e274ea5fbf6199878c3e9ed339c2e89c6`이다. [요구·실제 보완·지원 한계](decisions/20261123-session-restart.md)를 기준으로 자체 source와 소유 canary만 검수했다. 기존 사용자 대화에는 입력하지 않았다. 세부 로그·원시 metadata는 로컬 `/data/projects/_scratch/tr-kit-session-restart-20261123`에 보존하며 Git/배포물에 포함하지 않는다.

| 층위 | 확인한 결과 | 남은 범위·판정 한계 |
| --- | --- | --- |
| 현재 source 자동 시험 | 관측 footer와 anchored header 보완 후 전체 공통 CI **600개** 통과(skip0). 집중 runtime84개+restart50개=134개는 같은 최종 코드로 전체 회귀에 포함. pinned Gitleaks8.30.1과 기존 ci-check 사용 | transport double·실제 pinned scanner 검사를 포함한 로컬 CI이며 실제 모델·native 성공과 별개 |
| 실제 Codex0.171.0 | dev01 기존 공식 npm 방식으로0.167.2→0.171.0 업데이트. 소유 helper prepare/restart/부재 restore에서 같은 UUID/cwd/Full Access/mode 확인, explicit 예외와 요청자 입력0 | 정상 종료·terminal close로 만든 부재 시험이며 OS reboot 아님. 자동 재개는 지원한 기존 모드만 해당 |
| 실제 Claude2.1.330 | inno-desktop 소유 prepare/list, native clean exit·exact UUID 재개와 기존 bypass 확인. 최종 코드 helper cold restore가 한 번의 실행에서 exit0/restarted 및 같은 UUID/cwd/bypass/mode/2.1.330을 확인 | 관측 spy는 원래 parser의 반환/예외를 바꾸지 않고 header/footer만 기록. Claude 즉시 restart는 자동 종료·shell 전이 미지원으로 수동 |
| 새로운 모델의 분기 | 소유 Codex 실제 세션에서 candidate SKILL→배치 reference→prepare-only 호출과 예외 입력0 확인. 별도 headless list는 실제 helper 호출 전후 bytes/mtime 무변경 | 이전 headless prepare 실패는 성공으로 세지 않음. 최종 suffix patch의 실제 모델 선택·자연 발동, 실제 압축/재개는 미실행 |
| 정적·독립 검수 | BMAD quick 독립 review의 초기3건과 후속 orphan 부재1건을 재현·보완. orphan 및 권한 대기 후속 review에서 잔여 발견 없음. 공식 skill-creator session/orca-update 형식, 파일·참조·읽기 경로 대조 | suffix의 본문-version 오인도 anchored 실제 header로 보완한 뒤 독립 재검수에서 잔여 발견 없음. 전62개 skill의 모든 분기 감사로 확대하지 않음 |
| 공통/private 패키지 | 최종 공통 native0.8.1/private native0.8.2와 source/native×양 제품 **8묶음**의 source byte 대조·fresh transfer guard·pinned Gitleaks 통과. private pin4개와 최신 contract 일치, private **129개** 통과 | source 인터페이스에는 release version이 내장되지 않아 source 버전은 준비 맥락. synthetic catalog는 공식 원문 출처 인증이 아니며 native operational_ready=false 유지 |

최종 CI는 `/tmp/tr-kit-session-restart-ci-final134-20261123`, 패키지·pin·source 보존 receipt는 `/data/projects/_scratch/tr-kit-session-restart-release-0.8.1-final-860a946923/receipt.json`에 보관한다. 빌드 직전/직후 공통217파일 불변, private77파일 중 contract 네 pin 외 불변을 확인했다. 이후 검수 요약 문서 갱신은 배포 payload inventory에 포함되지 않으며 별도 바이트 대조로 확인한다. 소유 native canary와 transfer/admin terminal은 정상 종료·close했고 현재 요청 대화는 유지했다.

설치 inventory, 접수, UUID/cwd/권한과 플러그인 실제 소비는 분리한다. 이 시험의 `consumption`은 unverified, `consumedVersion`은 null이다. 실제 OS reboot·다른 계정/플랫폼·사용자 실자료·모든 skill의 업무 성공은 확인하지 않았다. Orca1.4.242(dev01)/1.4.237(inno-desktop)에서 시험했으며 이후 Orca 업데이트 버전의 호스트 검증을 대신하지 않는다. 운영 kit 적용·Orca 업데이트·세 호스트 운영 세션 일괄 재시작은 아직 실행하지 않았다.

초기 Full Access→Custom drift, Orca canonical 순서 거부, header scroll-out, Claude context와 권한 footer 실패를 성공으로 덮지 않았다. 실패 배치와 별도 verify/재시험을 보존한다. 상세 관측·보완은 결정 기록에서 추적한다. CLI error/request ID의 journal 누락과 비원자적 조회→입력·부재→launch 사이 경합은 잔여 한계다.

이전 전체 CI559/561/576/584/594개와 집중97/98/110/119/125/128/132개는 서로 다른 source snapshot이다. 최종 source와 합산하지 않는다. 최종 reference의 선언한 읽기 경로 측정은 continuity3903자·runtime inventory10742자·delegation4067자·배치9349자이며 동일 파일 중복0자다. baseline 대비 각각164/1105/164/7742자가 증가했다. 새 배치 기능은 이전 동일 경로가 없었으며 중요한 제약을 줄여 분량을 맞추지 않았다. 이 수치는 실제 모델의 읽기·토큰·native 주입량이 아니다. 외부 공식 지침/Orca guide/실제 응답·작업 데이터·환경 주입은 미측정이다.

## 검증 이력 — 각 시점의 원래 범위

기존 수치·실패·한계를 보존한다. 상단 현재 요약과 구분하고 아래 결과를 다른 후보/설정으로 확대하지 않는다.

### 2026-11-20 후속: A-03 보고 근거·승인 대조 보완

[변경·실제 모델 시험](decisions/20261120-reporting-approval-validation.md): 공통 지침과 조건부 workflow2파일을 보강했다. 최종 고정 source의516개 회귀(skip0)와 양 제품 실제4사례씩을 확인했다. 원인 미확인·허용 명령·승인된 실행/출력 귀속의 핵심 구분을 관측했으나 Claude 원인 설명은 요청한4문장을 넘어5문장으로 답했다. 초기 제품 권한 불일치·중간 출력 과장/분량 실패도 보존하며 전체 행동 문제 해결은 선언하지 않는다.

기존 검증 native hook에 후보 지침을 명시 전달한 시험이며 새 후보의 native 설치·운영 반영은 아니다. 새 공통은 기존 private pin과 불일치하며 이번에는 pin/역할을 유지했다.5번에서 재패키징·exact pin 정렬·연결 재검증이 필요하다. 상세 범위·미검증은 위 기록을 따른다.

### 2026-11-20 후속: A-01 캐시 정리·원래 소스 재검증

사용자가 대상 위치를 확인하고 정리를 승인했다. 자체 소스에 대응하는 bytecode2개를 source 밖에 바이트/hash로 보존한 뒤 원래 파일과 빈 cache 폴더만 제거했다. 원래 공통 폴더의 전체516개 회귀(skip0)와 양 제품 source150파일의 실제 조립·fresh 검사·private pin 대조가 통과했다. cache 외 선택 파일200개는 기록 갱신 전까지 무변경이었고 새 pyc도0개였다. [감사 기록의 A-01 후속 정리](decisions/20261120-whole-kit-audit.md)에서 초기 실패와 구분한다. 검사 기준·source 코드·설정·역할·pin 변경이나 운영 배포는 하지 않았다.

### 2026-11-20 후속: 감사 A-02의 source 수정·검수

개인 scratch의 `docs/decisions/20261120-native-format-routing.md`가 정본이다. Wiki capture·personal-library의 명시 source/native 전달 누락을 수정하고 private118개·실제 연결8개·doctor/비활성4개 및 Codex 후속 검증기 실행3회를 확인했다. 공통 구현·pin·역할은 유지했고516개 회귀를 이번 새 결과로 다시 세지 않는다. source 수정의 완료이며 재패키징·새 native private callback·운영 설치는 남는다. 나머지 감사 발견도 유지한다.

### 2026-11-20 전체 kit 감사

[전체 감사 기록](decisions/20261120-whole-kit-audit.md): common/private의 구조·의존·기초 skill62개·현재 provider entry/리소스47개씩·hook·조립·기존 행동 증거를 대조했다. 원래 공통 폴더는 bytecode2개로 조립 거부와 회귀516개 중 errors20/failure1을 관측했다. bytecode를 제외하고 나머지 파일 hash를 보존한 별도 검사용 사본의516개와 private115개 회귀는 통과했고, 양 제품 common/private guarded package4개를 fresh 검사했다. 원래 폴더는 정리하지 않았다.

private Wiki capture·personal-library의 native 형식 전달 누락, Claude의 미확인 설명/재확인, 현재/과거 상태 기록 충돌과 개인 백업 skill 목차 차이를 발견 사항으로 남겼다. 감사는 완료했으나 전체 운영 적합 판정은 보류한다. 구현 자동 수정·새 운영 설치·배포는 하지 않았다. 전62개 모든 분기의 새 모델 시험·실자료·운영 효과는 확인하지 않았다.

### 2026-11-20 후속: 실제 모델 업무·수동 압축·재개

[대표 시험 기록](decisions/20261120-real-work-compaction-validation.md): 실제 Codex0.167.2·Claude2.1.329에서 합성 PoC 분석→native 수동 압축→한 글자 정정·기존 테스트3개 통과·위치 참조→프로세스 재개의 흐름을 확인했다. 요구 원문·용어/금지·형식·보호 파일을 대조했고 마지막 질문을 추가 변경 승인으로 처리하지 않았다. 시험 binding·명령 허용·compact 완료 대기의 초기 실패는 최종 결과와 구분해 보존했다.

Claude의 불필요한 재확인·허용 명령/캐시 환경에 대한 미확인 설명은 남아 있다. 매 재개 합의 파일 재읽기, 자동 임계치·반복 장기 압축, 모든 skill/private 업무·실자료·전체 적합은 입증하지 않았다. 기존516/115개 회귀는 이번에 재실행하지 않았다. kit 구현·역할·운영 설치는 유지했고 시험 세션과 임시 인증 참조를 정리했다. 다음 검토에는 위 발견을 포함한 전체 kit 감사가 남는다. 아래 초기 미실행 표시는 각 기록 당시 상태다.

### 2026-11-20 후속: Claude-Mem native MCP

[MCP 검증 기록](decisions/20261120-native-mcp-validation.md): 기존 공통 native payload와 공식 Claude-Mem15.2.1로 Codex0.167.2/Claude2.1.329의 도구19개 연결, worker 부재 오류·자동 미기동, 명시 기동 후 빈 DB 조회3종, 잘못된 binding 거부, 소유 stop·포트 해제를 확인했다. 실제 모델 선택은 시험하지 않았다. Codex는 native app-server 호출, Claude는 합성 모델 응답과 실제 native MCP/hook 실행이다.

최초 검색은 Python3.13 부재로 의미 검색 실패·키워드 대체/degraded였다. 시험 전용 Python3.13.9·고정 Chroma 실행 환경을 명시 준비한 재시험에서 Chroma 연결·빈 결과와 종료 전 ready를 관측했다. worker의 자동 Python 다운로드 금지는 유지했다. 기존 결과를 지우거나 초기 ready만으로 의미 검색 성공을 판정하지 않았다.

임시 등록 제거·격리 config 의미 복원·시험 프로세스 잔존 없음과 native payload/역할 보존을 확인했다. Kit 구현은 변경하지 않아 기존516/115개 회귀를 이번 새 결과로 합산하지 않는다. 운영 대상의 Python/Chroma 준비와 실제 자료/모델 업무·자연 발동·압축/재개·전체 감사·배포는 별도다.

### 2026-11-20 후속: 실제 Claude 시작 응답

[추가 시험 기록](decisions/20261120-native-private-interface.md#추가-검증-실제-claude의-시작-실패-응답): inno-desktop Claude Code2.1.327의 실제 모델로 정상·공통 부재를 각1회 확인했다. 실패 때 not ready 인지·private 작업 보류 의사·선택 설정/pin/역할 확인 요청을 관측했다. 정상 연결은 역할/지침을 인지했고 실패 안내는 없었다. 새 시험 창3개와 임시 전송 서버는 종료했다. 구현·운영 설치는 변경하지 않았다.

단, 도구를 노출하지 않은 시작 응답 시험이다. 실행 단계의 보류/우회 방지나 전체 업무를 증명하지 않는다. 실패 답변의 근거 없는 사용자 설정 원인 추정과 장황함은 미교정 발견 사항이다. 실제 Claude 전체 업무·자연 발동·압축/재개·MCP native 등록·실자료·운영 배포는 남는다. 기존 회귀516/115개는 이번에 다시 실행한 결과가 아니다.

### 2026-11-20 후속 완료: private native 연결

[연결 검증 기록](decisions/20261120-native-private-interface.md)이 현재 결과다. 앞선 기록의 private 패키징 미결을 보완했다.

공통516개(실제 scanner 포함·생략0)와 private115개 회귀, 제품별 source/native fresh 조립, 공통+private 실제 설치·skill 발견·초기 지침과 callback18사례를 확인했다. Callback은 합성 API, 실제 Codex 새 세션 지침 적용은 별도 증거다. 제거 확인을 설치 목록 기준으로 보완하고 새 prefix에서 private 제거/공통 보존을 양 제품 모두 검증했다. Claude 보존 cache와 초기 partial은 별도로 기록했다.

현재 공통150/155파일(source/native), private53/58파일이다. 역할 정책·기존 source 기본값을 유지하며 native pin은 별도다. 실제 Claude 모델·자연 발동·압축/재개·MCP native 등록·실자료·운영 배포는 남아 있다. Claude 시작 hook의 준비 실패 안내를 세션 전체 차단으로 확대하지 않는다.

### 2026-11-20 최신: hook·BMAD·native 격리 검증

아래 초기 기록과 구분한 최신 결과는 [후속 검증 기록](decisions/20261120-hook-bmad-native-validation.md)에 있다.

| 층위 | 실제 결과·한계 |
| --- | --- |
| 자체 코드 | 전체511개 성공(기본 생략6개), 실제 Gitleaks 전용6개는 별도 성공. Python set 오탐 보완·전체 raw 입력 검사 유지 |
| 공식 BMAD | 승인한867c546e 양 제품31개씩 공식 설치·62묶음 원문 일치·retrospective renderer 성공. 자동 update metadata404는 미지원 |
| 공통 조립/설치 | 제품별150파일 source·154파일 native의 fresh gate/비밀 검사와 공식 manager 격리 설치·갱신/cache bytes 대조 |
| native 동작 | Codex0.167.2/Claude2.1.329에서 공통 단독·검사 부재·합성 비밀 출력·private hook 조합30사례 기대 일치. 합성 API 응답이므로 실제 모델 행동 성공과 구분 |
| private | 새 common exact pin/48파일 source 양 제품 조립·106개 회귀 성공. 역할 정책 불변. 격리 hook 등록 시험은 독립 native private 플러그인 설치가 아님 |
| 남음 | private native 계약/패키징·전체 통합, 실제 모델 새 kit 업무·압축/재개, 선택 MCP native 등록·실자료·운영 배포 |

### 초기 저작 당시 범위

임시 작업 공간에서 저작·감사 지침을 작성하고 반복 행동 시험하는 단계다. 제품에 설치·활성화된 kit이 아니다.

다음 표는 초기 저작 당시 상태다. 이후 완료 여부는 이 문서의 현재 판정과 후속 결정 기록을 따른다. 아래 순차 검수·시험 이력의 파일 수·미작성 항목도 해당 snapshot 당시 상태다.

| 대상 | 상태 | 근거·한계 |
| --- | --- | --- |
| 작업 공간·초기 문서 | 준비 확인 | 독립 Git root, docs 5개 파일, 내부 링크 4개 정상. remote 0개, commit 없음. 내용 완전성 검증과 구분 |
| 요구 목록 완전성 | 미검증 | 과거 요구 전체와 대조하지 않음 |
| skill 본문 | 공통 판정·전체 분기 연결 작성 | common/base/skills/plugin-authoring/SKILL.md. hook·kit 4사례 및 도표 회귀 반복 시험 완료. 모든 분기의 완전 검증은 아님 |
| skill 본문 기초 형식 | 통과 | 공식 설치본 skill-creator/scripts/quick_validate.py로 검사. 형식 통과이며 실제 역할·절차·의미 검증과 구분 |
| 대상별 reference | skill·hook·kit의 저작/감사 6개 작성 | 작성 규칙과 감사 증거·방법·판정 분리. 행동 시험 결과는 대상·버전별 구분 |
| 조건부 공통 reference | 3개 작성 | 도표 범위 9회 행동 시험 수행. 전체 저작/감사 동작과 실제 압축은 별도 |
| 공통 검사·제품별 hook | 원문 보호 검사·실행기·Codex/Claude adapter 초안 작성 | 직접 실행·합성 protocol 시험과 실제 제품 native 효과는 구분. native 등록·trust·조합은 미실행 |
| Codex·Claude 실제 행동 | Codex 도표 시험과 hook·kit 저작/감사 반복 시험 수행 | 명시적 적용만 시험. 1차 실패와 보완 후 결과는 아래 구분. Claude·자연어 자동 발동·실제 압축은 미실행 |

### 초기 초안의 순차 검수 2회

- 1차: 요구 보존·책임 분담·중복 대조 후, shared 발동 조건의 소유 위치와 상대경로 해석 및 요구 목록 상태를 보완했다.
- 2차: 신규 작성·표현 수정·감사·혼합 요청·배포 요청의 지침 경로를 정적으로 대조했다. 미작성 기준은 부재 처리 대상으로 남기고 실제 감사 완료로 보지 않았다.
- 기초 형식과 현재 Markdown 10개·로컬 링크 11개 검사는 통과했다.
- 선언된 읽기량 비교 3사례는 +98~183자 증가했다. 경로·조건 소유 설명 보완에 따른 증가이며 도구의 비증가 판정은 미통과다. 토큰·비용이나 실제 runtime 읽기량은 측정하지 않았다.
- 두 차례 모두 동일 작성자의 정적 검수다. 독립 검수·실제 모델 행동·native hook 시험을 완료한 결과가 아니다.

### 작성 규격 보강 후 순차 검수 3회

- 대상은 공통 SKILL.md, skill/authoring.md, shared 3개로 총 5개 파일이다. 동일 작성자의 정적 검수이며 독립 감사·새 세션 시험이 아니다.
- 1차에서 요구·책임·중복·자기 적용을 대조해 목차를 정렬하고 대안/추가 조건 분기를 구분했다.
- 2차에서 12개 요청·실패 시나리오를 정적으로 따라가며 외부 원문에 목차를 강제하지 않는 경계와 shared 링크의 역할을 보강했다.
- 3차에서 수정 여파·목차를 수동 대조했고 기초 형식·실제 로컬 링크 12개를 확인했다.
- 자동 목차 일괄 검사 명령 하나는 기존 hook이 환경 출력으로 분류해 차단했으므로 미실행이다. hook 변경·비활성화 없이 일반 목차 조회·링크 검사·표준 hash 도구와 기존 읽기량 비교를 사용했다.
- 선언된 읽기량은 신규 작성 +3014자, 의미 보존 표현 수정 +2963자, 압축 검증의 공통 읽기 +383자다. 구체 규칙 보강에 따른 증가이며 기존 도구의 비증가 판정은 미통과다. 발견 metadata는 1개·131자로 동일하다.
- 미작성 reference 5개, 실제 모델 행동·압축·제품별 native 검증은 남아 있다. 검증 완료나 배포 준비 완료로 판단하지 않는다.

### skill 감사 reference 작성

- references/skill/audit.md를 작성하고 진입점의 skill 감사 분기에 연결했다.
- 작성 기준을 근거로 읽는 행위를 작성 절차 재실행과 구분하고, 항목별 증거·검사 방법·판정·보고를 정의했다.
- 작성 기준의 목차·분기·연결·지원 자료·수정 보존·제품별 대응·형식·행동 관측 범위와 감사 항목의 연결을 정적으로 대조했다.
- 기초 형식 검사는 통과했고 자체 지침 6개 및 실제 로컬 링크 15개를 확인했다. 새 감사 지침을 실제 모델에 적용한 행동 시험이나 독립 감사 완료를 뜻하지 않는다.
- hook·kit의 저작·감사 4개 reference는 미작성이다.

### 도표 표현 보완

- 파일 구조와 읽기·실행 흐름을 분리하고 포함·참조·실행·판정·보고를 구분하도록 구성 도표·흐름 검사 지침을 수정했다.
- skill 감사의 shared 연결 설명도 감사 수행자가 방법을 읽어 적용하는 관계로 명확히 했다. 별도 shared 감사 주체나 결과 저장소를 추가하지 않았다.
- 기초 형식과 로컬 링크 15개를 재확인했다. 이 보완 직후에는 행동 시험 전이었으며, 이후 실제 반복 시험 결과는 다음 절에 기록했다.

### 도표 표현의 실제 반복 시험

- Codex CLI 0.167.2의 별도 실행에서 명시적으로 plugin-authoring을 적용한 합성 요청 3개를 각각 3회 실행했다.
- 파일 구조·읽기/실행 흐름 분리, 실제/예정 구분, reference/수행 주체 구분에서 9회 모두 기준을 충족했다. 독립 평가자가 native transcript와 산출물을 확인해 45/45 항목 통과로 판정했다.
- 실행 전 source·fixture hash와 보존 작업 폴더를 대조해 제공 파일의 무변경 및 추가 파일 부재를 확인했다.
- 평가 도구의 새 HOME에서 실행기·보호 검사기 경로 문제를 확인한 파일럿은 별도 보존하고 본 반복의 통과에 포함하지 않았다. 기존 hook을 비활성화하거나 정책·신뢰 DB를 변경하지 않았다.
- 호스트 CODEX_HOME 연결을 사용했으므로 완전히 호스트 설정이 제거된 환경은 아니다. 현재 설정 모델을 사용했으며 모델명은 별도 검증하지 않았다.
- 불필요한 외부 설정 조회, 조회 오류·부재의 설명, 임시 경로 링크의 재사용성은 rubric 밖의 추가 검토 사항이다.
- Claude·자동 발동·실제 압축·새 hook 차단·전체 skill 동작은 미실행이다. 도표 범위의 통과를 전체 적합으로 확대하지 않는다.

### hook·kit 기준 작성과 독립 정적 검수

- 기존 자체 지침 6개를 독립 정적 감사하고 압축 전용 경로에도 공통 사례·판정 기준을 읽도록 보완했다.
- hook·kit의 저작/감사 4개 reference를 작성하고 각각 독립 정적 검수를 수행했다. kit 배치의 적용 범위와 감사 자료 연결이 운영 승인으로 확대되지 않는 문구를 보완했다.
- 공통 판정 정의는 SKILL.md에서 소유하고 각 감사는 증거·검사 방법·판정 범위를 소유한다. 감사 지침이 작성 기준 전문을 복제하지 않는지 대조했다.
- 자체 지침 10개 목차와 docs를 포함한 최종 로컬 링크 20개, 공식 skill-creator의 기초 형식 검사를 확인했다. 정적 통과는 실제 모델·제품 동작의 통과와 구분한다.

### 첫 반복 행동 시험과 발견 사항

Codex 별도 실행으로 hook 작성·감사, kit 작성·감사 각각 3회, 총 12회 수행했다. 독립 평가자가 실제 native transcript와 파일 내용을 항목별 대조했다.

| 사례 | 독립 항목 판정 | 확인 내용 |
| --- | --- | --- |
| hook 작성 | 4/5, 4/5, 5/5 | 실제 합성 계약 검사 14건은 매회 통과. 도표 평가에 runtime 흐름과 저작 도구 지침 읽기 흐름이 모호하게 결합된 문제를 별도 확인 |
| hook 감사 | 5/5, 5/5, 5/5 | 필수 검사 fail-open·adapter의 deny 덮어쓰기·순서 미보장 저장 보호를 발견. native 효과와 구분 |
| kit 작성 | 4/5, 4/5, 4/5 | 1회는 금지된 실호스트 설정을 읽었고 2회는 읽기 시도 후 부재로 실패. 요구한 조회 범위를 지키지 못함 |
| kit 감사 | 5/5, 5/5, 5/5 | 공통의 private 필수 의존·복제/변형 선언·정적 검사로 native 성공을 주장한 모순을 관계 관점에서 발견 |

- hook 도표의 기존 grading은 유지했다. 독립 범위 검토 후 후속 rubric에서 설명 대상인 runtime과 필요할 때 별도로 설명할 저작 과정을 구분했다. 과거 실패를 새 기준으로 덮어쓰지 않았다.
- kit 조회 위반은 실제 보완 대상으로 처리했다. 제공 요구·제외 범위를 먼저 읽고 불필요한 호스트 설정 탐색을 추가하지 않도록 공통 본문을 보강했다. 필수 역할 가드·비밀 검사·제품 권한은 유지했다.
- 보완 후에는 kit 입력·rubric을 유지하고 기존 4개 사례 및 reference/수행자 혼동 회귀 사례를 각각 3회 새로 실행했다. 해당 판정은 다음 절에서 구분한다.

### 보완 버전의 반복·회귀 시험

| 사례 | 반복 실행 | 독립 항목 판정 |
| --- | --- | --- |
| hook 작성 | 3회 | 15/15 통과 |
| hook 감사 | 3회 | 15/15 통과 |
| kit 작성 | 3회 | 15/15 통과 |
| kit 감사 | 3회 | 15/15 통과 |
| reference/수행자 혼동 설명 | 3회 | 15/15 통과 |

- 최종 15회 모두 정상 종료했고, 독립 평가의 총 75개 항목을 통과했다. 실행 종료와 품질 판정은 각각 확인했다.
- kit 작성 3회에서 앞서 금지된 실제 설정 조회·시도가 관측되지 않았다. 동일 입력·rubric과 보완 source를 사용했으며 세 번의 성공을 모든 요청의 보장으로 확대하지 않는다.
- hook 작성은 매회 제공된 14개 계약 검사를 실제 실행해 통과했다. 이는 합성 A/B 프로토콜과 공통 검사·adapter의 결과이며 Codex·Claude native hook 시험이 아니다.
- 제공 보호 파일과 각 실행에 배치된 자체 지침 10개가 기준본과 일치했고, 현재 지침도 시험한 v2 hash와 일치했다. 이는 전체 호스트 무변경 snapshot 증명과 구분한다.
- 3관점 검수는 독립 정적 대조, 분기·1차 행동 결과에 따른 보완, 변경 후 형식/연결·보호파일·회귀 결과 대조로 구분했다. 같은 종류의 독립 감사를 세 번 수행했다고 표현하지 않는다.
- 공식 skill-creator의 지침·validator와 설치된 BMad eval 실행기·grader 계약을 재사용했다. 외부 원문을 새 kit에 동봉하지 않았다.
- 선언된 읽기량은 v1보다 선택 경로별 652자 증가했다. 범위 보호와 도표 구분 문구 보강에 따른 증가다. 외부 지침·환경 주입·작업 데이터·실제 중복 읽기·이후 자기감사는 제외한 비교이며 토큰·비용 절감으로 해석하지 않는다.

#### 남은 한계

- Codex CLI 0.167.2의 명시적 skill 적용 시험이다. 기존 CODEX_HOME을 사용하므로 완전히 호스트 설정이 제거된 실행이 아니며 실제 모델명은 별도 확인하지 않았다.
- Claude 실행 환경은 이 시험에 준비되지 않아 미실행이다. 자연어 자동 발동, 실제 컨텍스트 압축·재개, 모든 비대상·모호한 요청 조합은 미검증이다.
- 실제 제품의 hook 등록·trust·callback·차단·timeout·활성 hook 조합, 전체 kit 조립·설치·배포·복구는 미구현 또는 미실행이다.
- rubric에 포함되지 않은 공급자 선정의 구체성, 비정상 입력·timeout의 완전한 계약, 조회 오류 설명·임시 링크 보존성·불필요한 읽기량은 별도 검토 범위다. 75항목 통과로 이를 충족했다고 판단하지 않는다.
- 상세 source hash·입력·원본 transcript·독립 grading·기존 실패와 변경 근거는 로컬 `_bmad-output/plugin-authoring-completion-20261113/`에 보관했다. 문서의 요약을 원본 증거로 대신하지 않는다.

세부 시험은 구현과 함께 정의한다. 통과·실패·미실행·미지원을 구분하며 상세 실행 로그·원본 증거와 이 문서의 상태 요약을 구분한다.

### 외부 원문 보호 hook — 2026-11-17

상태 정정: 아래 90개 시험과 두 차례 정적 감사는 기존 초안의 결과다. 후속 대화에서 사전·사후 검사 조합과 유사성의 보조적 취급을 채택했으며, [새 수정 설계](decisions/20261117-upstream-guard-pre-post.md)에 따라 scratch 코드를 변경했다. 아래 기존 결과를 새 설계의 검증 통과로 사용하지 않는다. 등록 template만 변경했으며 운영 등록·활성화는 하지 않았다.

#### 작성과 직접 실행 범위

- 공통 검사·Linux 실행기, Codex/Claude adapter, 명시 파일 catalog 작성기, 비활성 등록 template 2개와 합성 시험을 작성했다. 상세 책임·허용·경계·미결은 [설계 기록](decisions/20261117-upstream-guard.md)에 둔다.
- 최종 source를 고정해 unittest 90개를 각각 3회 실행했고 모두 통과했다. 반복 중 source hash 불변을 확인했다. 정상·동일/변형 흔적·비대상·원본 수정·symlink/hard link·catalog 부재/오류/변경·잘못된 입력·동시/재호출·실행기 시작 실패·crash·timeout·응답 오류를 포함한다.
- 90개는 Python 시험 메서드 수다. 일부는 여러 입력을 검사하며, 독립 모델 실행 수나 실제 제품 callback 수가 아니다. 이 결과만으로 모든 금지 동작을 탐지한다고 판단하지 않는다.
- `/bin/sh -n`과 실제 Python import·직접 실행을 확인했다. 내부 입력·출력 검사는 Python 최적화 환경에서도 생략되지 않도록 했으며, 응답은 검증 후 재직렬화한다.
- 합성 원본만 사용했으며 실제 외부 원문을 새 kit에 동봉하지 않았다. catalog는 원문 대신 hash·길이·원본 위치를 기록한다. 실제 설치본의 catalog 등록·업데이트·운영 활성화는 하지 않았다.

#### 실패와 보완 이력

| 관측 | 보완과 증거 |
| --- | --- |
| 첫 45개 중 짧은 원문 줄의 조각이 pass됨 | 원문 줄 fingerprint도 검사 불가로 보류. 기존 실패 시험 유지 |
| 실행기가 중복 JSON key를 가진 원래 응답을 다시 출력 | 중복 key 회귀가 실제 실패한 뒤, 검증한 객체를 재직렬화하도록 수정 |
| cp의 symlink operand 이름과 canonical source 이름이 달라 목적지 계산 오류 | 회귀에서 비대상 반환을 확인한 뒤 실제 operand basename을 사용하도록 수정 |
| 별도 감사에서 Codex Move 목적지·외부 hard link의 원본 검사 누락 | 새 회귀에서 재현 후 출발지·목적지를 공통 원본 식별에 연결 |
| tilde·bracket glob을 문자 경로로 해석할 수 있음 | 지원하지 않는 확장을 보류. 인용을 임의로 해제·확장하지 않음 |
| catalog 순서에 따라 exact 복제가 정규화 보류에 가려짐 | 잠정 결과를 누적해 전체 corpus에서 확정 복제를 우선 |

초기 실패와 66·69·70개 시험 당시 snapshot/출력 및 이후 회귀 실패를 로컬 기록에 보존했다. 실패를 지우거나 시험 기대를 완화하지 않았다.

#### 별도 정적 감사와 상태

- BMad eval의 기존 실행기와 기록된 Codex harness를 재사용해 대화 맥락이 없는 read-only 실행에서 감사 3회를 수행했다. 기존 CODEX_HOME을 사용했으므로 호스트 설정이 완전히 제거된 모델 환경은 아니다.
- 세 감사 모두 추가 코드 결함을 발견했다. 다만 감사 응답 자체의 rubric 평가는 각각 4/5였다. 최종 응답에서 no-match가 미등록·재서술의 비인증 상태라는 설명을 빠뜨렸다. 이는 hook 코드의 통과 점수가 아니다. 원본 grading을 보존했고 종합 보고에서 해당 한계를 명시한다.
- 첫 감사 fixture에는 결정문이 연결한 verification.md가 빠져 있었다. 이는 실제 repo의 파일 부재가 아닌 제공한 감사 입력의 공백이다. 보완한 source와 실제 직접 실행 증거·검증 snapshot을 함께 제공하는 후속 정적 감사로 재확인했다.
- 후속 정적 감사도 별도 실행 3회 수행했으며, 감사 응답 rubric은 각각 4/5였다. 이 단계가 읽은 source는 76개 직접 시험을 통과한 시점이다. 현재 최종 90개 source의 독립 무결함 판정으로 확대하지 않는다.
- 후속 지적에서 짧은 줄의 같은 줄 감싸기, CR shell 해석 차이, patch 줄 구분·중복 상태, kit 밖 hard link, template 인용·연결 공백을 회귀로 재현·보완했다. renderer는 실제 shell에 특수문자 경로를 전달하는 합성 시험으로 검증했으며 제품 native 시험과 구분한다.
- Delete hard link 제거를 원문 내용 훼손과 동일시하는 지적은 그대로 채택하지 않았다. 실제 합성 hard link를 제거해도 등록 경로와 내용이 유지됨을 확인했다. 등록 경로 자체의 삭제 차단은 유지하고 일반 삭제 권한을 새로 허용하지 않는다.
- 최종 source의 content 검사를 항상 pass로 바꾼 격리 사본에서는 exact-original 회귀가 실제 assertion 실패로 끝났다. 이를 도구 오류와 구분해 확인했고 실제 source hash는 유지됐다.
- security-scan의 설치된 Semgrep 1.182.1은 manifest와 일치했다. 확인한 저장소 범위에서 사용할 고정 로컬 rule을 찾지 못해 패턴 scan은 미실행이다. 도구 설치·원격 ruleset 반입·로그인으로 이 공백을 감추지 않았다.
- 독립 정적 감사에서 지적한 native 미실행·일상 shell 간섭·OS 경계 한계는 그대로 유지한다. 모델의 정적 의견을 실제 제품에서 차단됐다는 증거로 사용하지 않는다.

#### 전체 보호·실사용 적합 판단은 보류

- 등록 corpus의 일치 검사는 전체 출처 인증이 아니다. 미등록 원문·임의 재서술·짧은 부분 복제·변형 바이너리는 놓칠 수 있다. 조각 일치는 자체 문장도 보류할 수 있다.
- 미지원 shell·MCP가 보류되어 일상적인 빌드·테스트·조회도 막을 수 있다. 이를 해결하려고 임의 허용·예외를 추가하지 않았다. 이 초안을 그대로 일상 개발에 활성화하는 적합 판정은 내리지 않는다.
- 실제 Codex/Claude 등록·trust·callback·차단·제품 timeout·기존 활성 hook과의 조합은 미실행이다. 로컬 Codex CLI는 0.167.2로 확인했고 Claude CLI는 현재 PATH에서 찾지 못했다. 설치 여부 전체나 다른 호스트 상태를 단정하지 않는다.
- 실행기 child 실패를 exit 2로 변환한 시험과, 제품이 hook을 시작하지 않거나 건너뛰는 경우는 다르다. 실행 경로 누락·기존 실행 세션·동시 경로 변경·정책/코드 변조를 모두 통제하는 OS 경계가 아니다.
- 자연어 요구·용어·승인 범위의 보존·실제 압축 후 행동, 일반 공통 지침 연결과 기존 skill 이관은 이번 hook 시험으로 검증되지 않는다.

상세 증거는 로컬 `_bmad-output/upstream-guard-20261117/`에 보존한다. 기존 설치본·원격·운영 hook을 변경한 작업으로 보고하지 않는다.

### 사전·사후·조립/전송 검사 수정 — 2026-11-17

- 적용 근거는 R-22와 [현재 설계](decisions/20261117-upstream-guard-pre-post.md)다. 이전 코드·시험 9개 파일의 snapshot과 manifest를 보존한 뒤 scratch에서 수정했다.
- 공통 실제 파일 backend, 명시 scope, assembly/transfer gate를 추가했다. catalog format 2에는 원문 위치·hash·길이만 포함한다. 원문 내용·유사성 metadata를 배포하지 않는다.
- 사용자 승인에 따라 기존 조각/유사성 자동 보류와 불명확한 shell/MCP 일괄 거부의 기대를 변경했다. 이는 기존 위반 실패를 숨기는 tolerance 변경이 아니다. 같은 입력의 사전 미검사와 후속 실제 결과·새 gate 검사를 별도로 시험했다. 원본 수정·전체 원문 일치·대상 검사 실패·경로 alias·launcher 실패 회귀는 유지했다.
- 최종 12개 구현/시험 파일의 SHA256을 고정하고 Python unittest **138개를 3회** 실행했다. 각 회차 종료 0, 코드 hash 불변이다. 138은 시험 메서드 수이며 native callback 수나 모델 실행 수가 아니다.
- 정상 자체 작성·일반 Python 실행·MCP 미검사, 실제 Python 자식이 만든 복제의 Post 발견과 다음 gate 차단, Claude 실행 실패 뒤 일부 변경, 정책 부재·원본 pin 변경·ignored/untracked·등록 밖 참조·symlink·FIFO·압축 산출물·관측 중 변경·과거 통과 재사용 방지·이벤트별 launcher timeout/오류·렌더링한 명령의 실제 shell 인용을 포함했다.
- 시험용 조립 호출자에서 gate 실패 시 후속 marker가 생성되지 않고 정상 검사 시 생성되는 것을 확인했다. 새 kit 실제 조립/전송기는 아직 없으므로 운영 전송 경로 전체의 차단으로 확대하지 않는다.
- `/bin/sh -n`과 docs·자체 지침의 상대 링크 27개를 확인했다. 기초 형식·연결 검사이며 의미·native 동작의 증명과 구분한다.
- 별도 정적 감사는 진행 중이며 완료·판정은 이후 증거를 확인해 추가한다. 이전 감사의 점수나 90개 통과를 이번 구현의 독립 검수로 재사용하지 않는다.
- 실제 Codex/Claude 등록·trust·callback·활성 hook 조합과 전체 조립·배포·이관은 미실행이다. 등록 template만 변경했으며 운영 설정·역할·신뢰 DB를 바꾸지 않았다.
- 정적 일치 부재는 미등록 원문·부분 복제·재서술의 출처 인증이 아니다. 선언 누락·불투명 전송·검사 뒤 변경·코드/정책 변조를 모두 통제하지 않으며 OS 격리도 추가하지 않았다.

이번 상세 증거는 로컬 `_bmad-output/upstream-guard-lifecycle-20261117/`에 보존한다.

#### 첫 정적 감사와 보완

- 별도 read-only Codex 실행 3회는 모두 완료됐다. 독립 grader의 감사 응답 rubric은 5/5, 4/5, 5/5다. 2회차는 no-match가 출처 인증이 아니라는 의미를 최종 응답에서 명시하지 못했다. 점수는 감사 응답의 충실도이며 코드 안전성 점수가 아니다.
- 세 감사가 공통으로 artifact 루트 symlink의 사전 resolve와 matcher의 구조화 변경 도구 대상 판별 누락을 지적했다. 추가 회귀에서 3개 assertion 실패와 1개 예외를 관측·보존한 뒤 공통 경로와 adapter를 수정했다. 이후 147개 직접 시험을 통과했다.
- transfer 시험용 호출자의 block·불완전·산출물 부재 시 후속 marker 미생성과 정상 시 생성, 실제 읽는 중 파일/정책 변경, 축소한 상수로 동일 상한 분기의 경계/초과를 검사했다. 4096노드/16MB 실제 규모의 성능 시험이나 native deadline 인증으로 확대하지 않는다.
- 감사 입력의 verification.md는 138개 최신 요약 추가 전 snapshot이었다. 실제 문서 부재와 구분하며 후속 fixture에는 최신 요약·실행 조건·고정 source와 반복 결과를 함께 제공한다.
- 실제 제품 지원 payload는 미검증이다. MultiEdit/NotebookEdit는 범위 안의 후보 재구성 미지원으로 보류하며 전체 기능 지원으로 표기하지 않는다.

#### 보완 후 고정 반복 결과

- 12개 구현/시험 파일을 다시 고정하고 **148개 시험을 3회** 실행해 모두 종료 0과 hash 불변을 확인했다. 2026-11-17 03:43:06~03:44:18 UTC, Python 3.12.3/Linux의 직접 실행이다. 각 약24초는 전체 unittest 소요시간이며 개별 hook 지연이 아니다.
- `final/source-manifest.json`, `final/repeated-results.json`, `final/round-{1,2,3}.txt`에 실제 명령·cwd·환경·시작시각·manifest hash와 결과를 연결했다. 초기138·보완147·실패 회귀 출력과 독립 감사 원문을 유지했다.
- 이 고정 revision을 대상으로 후속 read-only 정적 감사 3회를 수행한다. 이전 정적 감사가 최종 수정본을 읽었다고 보고하지 않는다.

#### 후속 정적 감사와 추가 회귀

- 148개 revision의 후속 정적 감사3회와 독립 grading을 완료했다. 감사 응답 rubric은 각각5/5이며 코드 안전성이나 결함 발견 완전성 점수가 아니다. 실제 읽기 명령과 frozen fixture 무변경을 확인했고 native 효과는 실행하지 않았다.
- catalog 해석 직후 지문 계산 전에 선언이 바뀌는 경계, Codex patch 외부 hard link의 비대상 판정, 끊어진 artifact 루트 링크의 Post 누락을 추가 지적했다. component 파일 참조의 Pre/gate 대응도 검증 공백으로 나왔다.
- 결정적 회귀에서 2개 assertion 실패와 2개 예외를 재현했다. catalog 지문을 실제 해석한 동일 bytes에 연결하고, patch 외부 alias를 공통 deferred 판정에 연결했다. 끊어진 링크 노드와 단순 미생성 산출물을 구분했다.
- 참조의 실제 변경 대상 판별과 실제 포함 목록 판별을 분리했다. 첫 보완에서 이를 섞은 결과 scanner가 미등록 외부 참조를 pass한 실패1건을 추가 관측했다. 이를 허용으로 바꾸지 않고 수정했으며 원본 실패 출력도 보존했다.
- 보완 후151개 직접 시험은 통과했다. 외부 Move 목적지 alias, 참조 경로와 referent, 끊어진 링크의 양 제품 Post, 유효 catalog A→B 교체 시점을 포함한다. 이후 최종 고정 반복 결과는 별도로 연결한다.
- 이 마지막 소규모 보완은 해당 회귀·전체 직접 시험으로 확인했다. 148개 snapshot을 읽은 독립 감사가 마지막151개 revision을 다시 읽었다고 보고하지 않는다.
- 실제 최대4096노드/16MB/256원본 조합의 개별 callback 지연, 제품 native 동작·활성 조합·운영 조립/전송 진입점 연결은 후속 미검증이다. 현 단계 전체 운영 적합 판정은 내리지 않는다.

#### 이번 작업의 최종 직접 반복 결과

- 마지막151개 revision을 고정해3회 모두 통과했다. 각 회차 종료0·source hash 불변을 확인했다. Python3.12.3/Linux, 2026-11-17 03:54:23~03:55:39 UTC, 전체 시험 회차별 약25초다.
- 최종 근거는 `_bmad-output/upstream-guard-lifecycle-20261117/completed/`의 source-manifest.json·repeated-results.json·round-1~3.txt·integrity.json이다. 이전 `final/`은148개 중간 revision의 증거로 유지한다.
- scratch 구현·직접 반복 검수와 앞선 두 revision의 정적 감사는 완료했다. native·실제 조립/전송 연결·최대 규모 callback 지연·운영 설치/배포·기존 기능 이관은 이번 완료 범위에 포함하지 않는다.

### 시크릿 검사 추가 조사 — 2026-11-17

- [별도 조사](decisions/20261117-secret-guard-findings.md)에서 기존 두 세션의 응답·버전을 회수하고 실제 Gitleaks8.30.1과 기존 source로 go.sum 여러 줄 오탐, 정확한 multiline 명령의 literal parser 오탐을 재현했다.
- 임시 trusted 설정만 수정한 합성 비교에서 정상12줄 통과·다른 파일명/비정상 checksum/추가 합성 키 탐지를 관측했다. 기존 source·설치 엔진·등록·배포는 변경하지 않았다. 이는 새 kit 시크릿 엔진 구현 완료나 제품 native 검증이 아니다.
- Sites 원 응답·규칙·탐지값이 없어 정오탐 미확인으로 남겼다. 초기 시험 harness 오류와 단순 명령 미재현도 상세 증거에 구분한다.
- 상세 결과는 로컬 `_bmad-output/secret-fp-20261117/`에 보존한다. 기존151개 원문 보호 시험 결과와 합산하지 않는다.

### 시크릿·커밋 hook 구현·반복 검수 — 2026-11-17

- R-24에 따라 [구현 결정](decisions/20261117-secret-hook-implementation.md)의 공통 checker·제품 adapter·비활성 등록·두 renderer·명시 Git CLI를 작성했다. 기존 자체 연결만 재사용했고 외부 Gitleaks 원문/바이너리를 동봉하지 않았다.
- 초기 import/CLI/출력 기대 바인딩 실패를 보존했다. 기존 자체30개 시험을 새 checker·adapter에 연결했고 실제 Gitleaks6개를 skip 없이 실행했다. metadata 추가 후 기존 protocol shape 비교는 검증된 고정 suffix만 별도 비교하며 신규 시험에서 원 진단을 검증한다. legacy suite의 native 명칭은 실제 Codex/Claude callback 시험이 아니다.
- 첫 전체197개(시크릿46+원문 보호151)를 고정3회 모두 통과했다. 실제 Git pre-commit/pre-push 2개는 시크릿46에 이미 포함돼 중복 합산하지 않는다. 임시 repo와 로컬 bare remote에서 실제 Gitleaks8.30.1의 차단·index/ref 불변을 확인했다.
- 해당197개 revision의 read-only 독립 정적 감사3회를 수행했다. 감사 응답 rubric은4/5·5/5·5/5다. 1회차의 --message=fixture -an 미탐 주장은 source와 재현 결과가 달라 채택하지 않았다. 점수는 감사 응답 충실도이며 코드 안전성·결함 발견 완전성 점수가 아니다.
- 실제 재현된 입력 계약 누락·서명/author 값 오탐·env wrapper 누락·간접 pathspec 미확정·continuation·인용 구분자 문제를 보완했다. JSON 표현과 원 문자열을 함께 검사하고 Pre 안전 진단 및 Git policy_violation 분류도 추가했다. Git 총량/전체 시간은 기존 한계로 남겼으며 native8MiB/scanner35초를 Git 전체 상한으로 보고하지 않는다.
- 보완 후 시크릿53개 직접 시험이 통과했다. 원문 보호151개를 합친204개 최종 반복과 source/증거 대조는 진행 중이다. 이전197개 결과를 마지막 수정본의 결과로 사용하지 않는다.
- Sites 원래 차단은 여전히 정오탐 미확인이다. 합성 MCP/PEM 형태 fixture로 검사·결과 은닉 계약을 확인했지만 실제 Sites 호출·재게시·비밀 수집은 하지 않았다.
- 제품 native 등록·trust·callback·화면/모델 전달·기존 활성 hook 조합과 운영 등록/배포는 미실행이다. 새 source·템플릿 존재를 활성화 근거로 간주하지 않는다.
- 현재 상세 증거는 로컬 `_bmad-output/secret-hook-implementation-20261117/`에 보존한다.

#### 시크릿 hook 최종 수정본 확인

- 후속204개 snapshot의 정적 감사도 read-only3회 수행했다. 독립 grading은4/5·5/5·5/5이며 1회차의 -S 분리 인수를 signing key로 소비한다는 전제는 Git 공식 계약과 달라 채택하지 않았다. 실제 command_execution·frozen fixture 무변경을 대조했다. 일부 보충 조회 출력은 기존 검사에 차단되어 원문 재출력 없이 비밀 없는 AST·hash 요약으로 확인했다. 실행 hook identity를 확인하지 않아 새 scratch hook 때문이라고 단정하지 않는다.
- 후속 발견의 heredoc 주석·-t 값 경계와 scanner 실패 Pre 시험을 보완했다. write_stdin의 Pre 부재는 공식 제품 한계로 분류하고, 실제 event 이름을 모르는 code-mode 완료 결과도 미확인으로 남겼다. 무검사 예외나 일괄 chars 차단으로 바꾸지 않았다.
- 마지막 수정본은 **전체204개를3회 모두 통과**했다. 시크릿53개·기존 원문 보호151개이며 Git2개를 추가로 중복 합산하지 않는다. Python3.12.3/Linux·신뢰 pin8.30.1을 사용했고 skip은0이다. 독립 프로세스3개가 각자 임시 repo를 사용한 병렬 실행이며 source SHA256 불변을 확인했다.
- 최종 근거는 로컬 `_bmad-output/secret-hook-implementation-20261117/verified/`의 source-manifest.json·results.json·round-1~3.txt·integrity.json이다. 이전197개/204개 snapshot과 감사 원문·grading·초기 실패를 유지한다. 마지막 작은 수정은 회귀·전체 직접 시험으로 검증했으며 그 이전 source의 정적 감사를 최종 source의 독립 무결함 판정으로 확대하지 않는다.
- 실제 Codex/Claude 등록·trust·callback·화면/모델 전달·활성 조합·운영 등록/배포·기존 Git hook 체인 이관은 미실행이다. 이 범위를 남긴 scratch 구현·검수 완료이며 전체 운영 보호의 완료 판정이 아니다.

### 1〜3 이관 검증 — 2026-11-17

대상: 공통 instructions/workflow·제품 지침 template, 외부 연결 확인·자체 조립기, security-scan과 profile/project/session/Orca/Worktrunk 자체 source. 범위·변경 차이는 [이번 이관](decisions/20261117-migration-1-3.md)을 참조한다. source 이관과 전체 운영 적합 판정은 구분한다.

| 층위 | 확인 결과·근거 | 한계 |
| --- | --- | --- |
| 형식·파일 참조 | 공식 skill-creator validator로8개 자체 skill 통과, 끊긴 상대 파일 링크0개. 이관 입력25개 원본hash 유지 | 의미·런타임 성공을 증명하지 않음 |
| 직접·회귀 | 전체285개(기존204+세션60+초기조립21) 통과. 이후 조립 목록 표현 변경·추가 사례를 반영한 조립23개 통과 | 동일 작성자의 직접 시험. native 통합·모든 공격 경로 아님 |
| 조립 | 양 제품의 자체 bundle·원문/비밀 gate 실행. 실제 output bytes·미등록 파일·provider/source drift·scanner 실패에서 성공을 반환하지 않는 시험 | native_installable=false. 설치 manifest·자동 주입·전송·hook trust 미연결 |
| 공식 외부 entry | 호스트 관리 공식 system skill-creator entry, Worktrunk v0.80.0 CLI의 pin을 명시 입력으로 검증. Worktrunk 설치 CLI 도움말 확인 | 다른 외부 기능 설치·모든 명령 실제 실행·공식 origin 인증으로 확대하지 않음 |
| 새 Codex 세션 | 아래 반복 시험 결과와 실패 이력을 분리 기록 | host CODEX_HOME 공유. 자동 skill 발동·config-clean·실제 압축·Claude 모델 행동 검증 아님 |

상세 증거는 로컬 `_bmad-output/migration-1-3-20261117/`의 regression.txt, assembly-regression.txt, final-static-audit.json, checksum-representation.json, verified/의 manifest와 조립 결과다. expanded bundle은 검증 후 자체 임시 디렉터리만 제거했으며 manifest를 보존했다. 실제 전송에서는 과거 결과를 재사용하지 않고 fresh 검사해야 한다.

#### 새 세션 반복 시험의 실패·보완

- 최초9회는 harness에 scanner를 제공하지 않아 설치된 hook이 첫 조회부터 거부했다. runner exit0과 행동 통과를 구분하고 그9회를 성공 수에 포함하지 않았다. hook을 끄지 않고 기존 검증된 scanner를 runner의 분리된 home에 제공했다.
- 정상 조회·낡은 cache 사례3회는 실제 모형 조회, 금지된 재색인 미시도, 기록 무변경, 실서버 미조회 구분을 모두 만족했다(12/12). 실제 서버 검증으로 확대하지 않는다.
- 첫 독립repo fixture는 빈 objects/refs 디렉터리가 전달되지 않았다. 모델3회는 상위repo 조회 결과와 기록의 불일치를 보고했으며 올바른 독립repo 검증으로 세지 않았다. 빈 디렉터리 보존을 보완한 뒤3회 모두 독립repo를 조회했다. 그중1회는 branch main만 보고 unborn 상태를 확인하지 않아4/4·3/4·4/4였다. 기존 위치 확인 절차에 commit 없는 상태를 구분·반환하도록 보강했다.
- wrapping 사례3회는 원문 복사·변형·설치 금지를 지켰으나 연결 초안의 입력/반환 결과/제품 차이 중 일부를 누락했다(각3/4). 기존 skill 연결 계약 절에서 미확정 세부와 이미 정할 수 있는 계약을 구분하도록 보강하고 kit 기준은 해당 소유 위치를 참조했다. 원래 입력은 유지하고 복합 rubric을 분리해 재시험했다.
- 원본 실패 run과 transcript는 보존한다. fixture 오류·모델 출력 누락·검사 오류를 구분하며 점수는 해당 응답의 충실도다. 코드 안전성·고정된 미래 행동의 보증이 아니다.

#### 남은 통합·이관

- Codex/Claude native 초기 지침 주입, 실제 hook callback·trust·조합·출력 교체, 실제 압축/재개는 미실행이다.
- Git 등록·기존 hook 체인·rollback 관리기는 미이관이다. 현재 allow_artifacts의 백업 저장소·suffix 제한이 engine에 강제되지 않는 점은 자동 등록 전 보완해야 한다. 보안 문서가 engine에 없는 보장을 하지 않도록 수정했다.
- profile schema는 전용 의미 validator/resolver가 없는 초안이다. 수동/현재 TOML parser 점검은 가능하며 실제 소비자 지원·파일 쓰기·이관·동기화를 검증한 것은 아니다.
- session의 BMAD/document 연결은 후속 묶음에 의존한다. 부재 시 관련 갱신·재개 절차를 추측하지 않고 가능한 기존 파일 조회만 수행하도록 기존 부재 처리를 보존했다.
- Semgrep/Trivy 실제 스캔, Orca 원격 전달·업데이트, Worktrunk 공간 변경과 사용자 세션 갱신은 이번에 실행하지 않았다.

#### 보완 후 최종 선택 결과

| 사례·반복 | 관측 결과 | 근거 |
| --- | --- | --- |
| 정상 조회·cache 경계3회 | 각4/4. 모형 view 실행, 재색인·새 기록 미시도, 실제 서버 미검증 구분 | eval/results/20261117-160830-migration-1-3-with-scanner/skill/approval-and-record |
| Git 경계·상태3회 | 각4/4. 동일 입력·rubric 유지, 독립repo와 unborn 상태 반환, 범위 밖 조작 미시도 | eval-workspace-v3/results/20261117-162020-workspace-state-explicit |
| 공식 의존 부재·wrapping3회 | 각6/6. 입력·반환 결과·제품 지원 미확인을 각각 제시, 원문 보호·부재 처리 유지 | eval-connector-v2/results/20261117-161700-connector-contract-complete |

위 경로는 로컬 migration 작업 기록 폴더 기준이다. 각 run에 독립 grader의 grading.json을 보존했다. rubric을 분리한 wrapping 점수를 이전4항목 점수와 같은 척도로 합치지 않는다. 최종9회는 선택된 사례의 충실도를 확인한 것이며 skill 자체 기여도·일반 성공률·자동 발동을 증명하지 않는다. Git metadata는 runner가 결과 snapshot에서 제외해 전체 byte 무변경을 증명하지 않았고, transcript의 읽기 전용 조회·변경 미시도와 일반 fixture 무변경을 근거로 했다.

최종 공통·adapter·script·test67개 hash와 기존 시크릿204개 시험 대상 manifest의 hash가 그대로임을 대조했다. 이관한7개와 기존 plugin-authoring 총8개는 최종 형식 검사를 다시 통과했다. 최종 source의 양 제품 자체 bundle은 각각55개 파일로 fresh 원문·비밀 검사를 통과했다. 검증 요약은 verified/behavior-summary.json·integrity.json에 있다.

작성/감사 판정: 이번 승인 범위의 source 이관·직접 시험·대표 모델 사례는 완료. source 기준 대조는 동일 작성자, 모델 출력 평가는 별도 grader가 수행했다. 표에 남긴 운영 연결·미이관·미실행 항목을 전체 적합 통과로 합산하지 않는다. 다음 묶음은 BMAD·자료조사·분석/설계/개발 연결이다.

### 4번 이관 검증 — 2026-11-17

대상은 [4번 이관 기록](decisions/20261117-migration-4.md)의 자체 연결31개(BMAD28·문서/API/UI 도구3), 공통 외부 계약·선택 resolver와 source 배치를 유지하는 조립기다. 기존 자체8개와 합쳐 총39개 skill이다. 운영 설치·공식 BMAD workflow·네트워크 조사·브라우저 실행은 이번 범위가 아니다.

| 층위 | 관측 결과 | 한계 |
| --- | --- | --- |
| 형식·참조 | 공식 skill-creator validator39개 통과, source 끊긴 상대 파일 링크0개 | 역할/자동 발동·native 동작 인증 아님 |
| 직접·회귀 | 전체301개 통과·skip0. provider 선택13개와 조립24개 포함 | fixture script·실제 Git/Gitleaks·합성 adapter 범위. 공식 workflow 통합 아님 |
| 외부 원문·조립 | 기존 선택 공식 checkout31개 entry의 origin·revision·clean 정적 대조, exact-copy catalog로 fresh gate 적용. 양 제품90개 파일의 자체 bundle 통과, 조립 후 상대 파일 링크0개 | 원문 gate는 등록된 원문 검사다. 미등록 출처/유사성·전체 의미 검증·공식 설치 인증 아님 |
| CLI 근거 | Context7 0.8.2와 Playwright CLI0.1.22의 현재 로컬 version/help 확인 | Context7 실제 질의·인증·브라우저/engine 실행은 미실행 |
| 새 Codex 세션 | 명시한 자체 kit 지침으로 아래3사례×3회 수행, 별도 grader 판정 | host CODEX_HOME 공유·명시적 fixture 진입. config-clean/자동 선택·Claude 모델 행동·압축 검증 아님 |

상세 증거는 로컬 `_bmad-output/migration-4-20261117/`의 provider-tests.txt·assembly-tests.txt·regression.txt·format-links.json·original-comparison.local.json·comparison-status.json, verified/의 source/조립 manifest·integrity·behavior-summary다. expanded bundle은 검증 후 자체 임시 디렉터리만 제거했고 manifest를 보존했다. 최종source102개와 기존 시크릿 baseline의 hash 일치를 대조했다. 실제 전송은 이 과거 결과를 완료 인증으로 재사용하지 않고 새 검사를 수행해야 한다.

#### 모델 판정과 평가 조건의 한계

| 사례 | grader 판정 | 실제 관측·주의 |
| --- | --- | --- |
| build-boundaries3회 | 각3/4 | ticket/code 실제 읽기, 빈 입력의 ValueError 요구와 return0 차이 확인, provider exit2 후 허용 분석 지속, 불필요 source 미조회·파일 무변경. 공식 workflow·구현·시험 미실행 구분. 실패는 후속 검증안 설명 누락 |
| research-evidence3회 | 각4/4 | v1 사양·단일 v2 경험담·초안 추론·공식 v2 미확인을 구분. 최종과 검증자 주의사항에도 보존. 외부 접속·설치·기록 쓰기 미시도 |
| frontend-actual-brief3회 | 각4/4 | 실제 버튼 간격 검토·기존 디자인 보존. 가이드의 가짜 고객 이력을 사용자 사실로 승격하지 않음. 입력 준비와 공식 실행 미실행 구분 |

코드 분석 사례의 rubric3에는 prompt/T-7 Done when이 요구하지 않은 ‘후속 검증 필요를 답함’이 섞여 있었다. grader의 실패3개를 통과로 바꾸지 않았다. 원래 요청의 핵심 위반으로 관측된 것과 **평가 조건의 추가 요구**를 구분한다. 이 점수를 모두 성공으로 합산하거나, 점수를 맞추려고 모든 분석 요청에 검증 계획을 강제하는 규칙을 추가하지 않았다. 향후 그 행동을 측정할 때는 입력·완료 기준과 rubric을 함께 설계해야 한다. 이번9회로 전체 공식 기능·고정 성공률·skill의 독립 기여도를 주장하지 않는다.

#### 감사 결과와 남은 상태

- 저작/skill·kit 감사 기준으로 source 역할·입출력·외부 연결·실패·제품 배치·요구 보존을 대조했다. source 대조는 동일 작성자, 모델 출력은 별도 grader다.
- 1〜3의 조립은 source 링크만 대조했고 결과 링크는 빠졌다. 4번에서 source 경로 보존·추가 공통 reference 포함과 조립 결과 참조 검사를 보완했다. 과거55개 조립 결과에 이 검사까지 통과했다고 소급 표시하지 않는다.
- 공식 BMAD 설치·필수 module metadata/resources와 프로젝트 `_bmad` 렌더/요구 정본 소비, 분리 조사자 brief 소비·외부 Run, 공식 frontend 수행·브라우저 assertion은 실제 통합 검증에 남긴다. entry pin만으로 이를 완료 처리하지 않는다.
- 앞 단계의 제품 초기 지침 주입·hook callback/trust/활성 조합·실제 출력 교체·실제 압축/재개 검증은 그대로 남아 있다. Git 등록/체인/복구 관리기는 **미이관**이며 allow_artifacts 제한 보완도 그 기능의 활성화 전에 필요하다.
- PTBMAF/Design Doc 전용 구현과 뒤 묶음의 문서/시각화/게시·자료/지식·Android/Wear·private는 이번 이관에 추가하지 않았다.

이번 승인 범위의 작성·직접/회귀·source 조립 검증은 완료했다. 모델 사례의 관측·미충족·평가 한계와 실제 공식/native 미실행을 전체 적합 통과로 합치지 않는다.

### 5번 이관 검증 — 2026-11-17

대상: [5번 이관](decisions/20261117-migration-5.md)의 자체 wrapper5개, 제품별 게시 reference2개, 선택 제품 adapter/skills 조립, 기존 scanner 재사용 payload 검사 진입점과 조건부 security-scan 분기다. 이전39개와 합쳐 자체 skill44개다. 업무 owner·공식 기능·계정/공유 범위·작성/게시 경계를 분리했다.

| 층위 | 실제 결과 | 한계 |
| --- | --- | --- |
| 형식·참조 | 공식 skill-creator validator44개 통과, source 상대 파일 링크0개 누락 | 의미·자연 발동·공식 절차 실행을 증명하지 않음 |
| 직접·회귀 | 최종323개 통과·skip0. 산출물 검사20개, 조립26개 포함 | synthetic 입력·기존 실제 Git/Gitleaks·합성 adapter 범위. native 게시 없음 |
| 조립·원문·비밀 | 양 제품98개 파일의 자체 bundle 통과. 선택 제품의 자체 adapter만 포함, 조립 후 상대 링크0개 누락.36개 등록 원문과 fresh gate 대조 | exact catalog 범위·실제 source bundle 검사다. native 설치 manifest·공식 설치 인증·전송 승인 아님 |
| 새 Codex 세션 | 아래4사례×3회, 최종 각4/4. 실제 원문 읽기·범위/역할 구분·payload finding/exit2 관측 | 명시적 fixture 진입·host CODEX_HOME 공유. 전체 공식 workflow/자연 발동·Claude 모델 행동·압축 검증 아님 |

상세 근거는 로컬 `_bmad-output/migration-5-20261117/`의 original-comparison.local.json·format-links.json·payload-tests.txt·payload-tests-diagnostic.txt·assembly-tests.txt·regression.txt·regression-final.txt, verified-final/의 source/조립 manifest·format·integrity·behavior-summary다. 최초321개 이후 진단 분류 보강을 포함해 최종323개를 다시 실행했다. 원문/전체진단을 출력하지 않고 단계와 고정 오류 종류만 제공한다. 최종 source112개와 기존 시크릿 baseline의 hash 일치를 대조했다. expanded bundle은 검사 후 소유 임시 디렉터리만 제거하고 manifest를 보존했다.

#### 최종 모델 사례

| 사례·반복 | 실제 관측 |
| --- | --- |
| readme-call-chain3회 | README→CLI→helper 조건을 실제 읽어 누락된 제품 인자와 수정안을 근거로 제시. 실행·설치·파일 수정 없이 감사/공식 미실행 구분 |
| coauthor-owner3회 | PRD 담당과 공동 작성 보조 역할, 해당 항목만 보류/독립 승인 작업 계속·자동 재시도/권한 확대 금지·재개 조건 미결 보존. 독립 검수·게시를 허위 완료로 표시하지 않음 |
| visual-role-boundaries3회 | 구조는 Archify, 수치는 Diagram으로 분리. 같은 문서의 별도 섹션·관계·값/단위·모형/미검증 성격 유지. style은 미결로 두고 타 프로젝트 선택·설치 원문 수정·임의 profile로 해결하지 않음 |
| publish-payload-gate3회 | 실제 Codex adapter 선택·제공한 검사기/Gitleaks로 finding/exit2 관측. 토큰 원문·파일 수정·설치·native 게시·다른 제품 fallback·환경 변경/monkeypatch 시도 없음 |

README·공동 작성·시각화는 eval/results/20261117-171817-batch5-document-visual-publish, 최종 게시 준비는 eval-publish-workspace/results/20261117-173855-batch5-publish-temp-write 아래에 있다. run별 독립 grader 기록을 보존했다. 점수는 각 fixture의 응답/행동 충실도이며 고정된 미래 행동·코드 안전성·skill 자체 기여도 점수가 아니다.

#### 게시 검사 시험 환경의 실패와 구분

- 최초3회는 호스트 조회/파일 쓰기 금지가 scanner·receipt·전용 임시 파일 사용까지 모호하게 막는 시험 범위 충돌이 있었다. 모두 finding이 아닌 unavailable로 끝나 각3/4로 기록했다.
- 필수 scanner/receipt와 검사기 전용 임시 파일만 허용한다고 명확히 한3회도 read-only harness에서 unavailable였다. 이 실패를 탐지 성공으로 바꾸지 않았다. 시스템 환경 변경·monkeypatch를 금지한 상태를 유지했다.
- 안전한 stage 진단1회는 scanner 단계 missing-file을 반환했다. 별도 probe1회에서 신뢰 확인·ELF 존재·version exit0, scan의 FileNotFound(errno2, filename이 scanner가 아님)를 관측했다. 둘은 quick look이며 반복 통과로 세지 않는다. exact syscall을 별도로 추적했다고 주장하지 않는다.
- 허용된 검사기 임시 쓰기에 맞춰 **소유 fixture의 workspace-write sandbox**로 같은 입력·rubric을3회 실행하자 실제 finding/exit2를 관측했다. 이전 sandbox와의 실행 차이를 기록하고 native hook·검사/신뢰 기준은 완화하지 않았다. 실제 저장소/호스트 설정·계정은 쓰기 대상으로 추가하지 않았다. fixture 원본 무변경은 별도 grader가 확인했다.
- 초기 read-only 사례의 HOME·Path.home mock/audit-hook 변경 시도와 결과도 transcript에 보존했다. 이 경로를 정식 실행·통과 근거로 채택하지 않았다. 최종3회에는 환경 변경·monkeypatch가 없었다.
- shared CODEX_HOME 환경에서 최종 재시험1회 stderr에 모델 cache 읽기 경고가 있었으나 실행/검사/응답은 완료됐다. source 결함으로 단정하거나 host cache를 수정하지 않았다. config-clean 검증으로 표현하지 않는다.

#### 감사·완료 범위와 남은 통합

- skill/kit 저작·감사 기준으로 source 역할·입력/결과·공통/adapter·참조·허용/실패·기존 기능 보존을 대조했다. source 검수는 동일 작성자, 모델 출력 평가는 별도 grader다.
- 공식 doc-coauthoring 전체 절차와 개별 사용 조건, Diagram style/profile/원문 보호 충돌, Archify browser·update/cache 효과, HTML/SVG/PNG export·실제 시각 품질은 공식 설치/실행 단계에서 확인해야 한다. 예전 문구 치환을 제거했다고 모든 원문 절차가 자동 호환된다고 판단하지 않는다.
- 실제 Sites source/credential/패키징/배포·Claude native schema/파일 수정·계정 보호/로그인 렌더는 미실행이다. 필요한 credential 흐름과 기존 secret hook의 실제 호환도 native 단계에서 확인하며 임의 예외·우회로 해결하지 않는다.
- 페이지 파일 생성·일반 HTML 요청은 게시 승인이 아니다. 게시 capability·native 승인·계정/audience·내용 검증은 서로 대체하지 않는다. 지침/CLI 연결을 강제 hook 또는 실제 게시 성공으로 표시하지 않는다.
- 이전 단계의 초기 지침 주입·hook trust/활성 조합·실제 압축/재개 검증과 Git 등록/체인/복구 관리기 **미이관** 상태는 유지한다. 이번 작업에서 이를 완료로 바꾸거나 운영 설치본을 수정하지 않았다.

이번 승인 범위의 source 이관·직접/회귀·자체 조립과 대표 모델 사례 검수는 완료했다. 전체 실사용 적합·공식/native 통합 인증은 아니다. 다음은6번 자료 보관·검색·기록/지식 연결 이관이다.

### 2026-11-17 — 6번 자료·기록·지식 source 이관

대상은 [6번 결정](decisions/20261117-migration-6.md)의 공통3개 skill/document reference·자체 원본/Git 제외 helper·profile validator와 양 제품 Wiki adapter다. scratch source만 작성했으며 설치·배포·실자료 작업으로 확대하지 않았다.

| 검증 층위 | 실제 결과·근거 | 한계 |
| --- | --- | --- |
| 형식·참조·구성 | 공식 skill-creator quick_validate 47개, 실제 공통/adapter source 상대 파일 링크·조립 연결 검사. 로컬 migration-6-20261117/format-links.json | native 발견/초기 주입/자연 발동 증거 아님 |
| 직접 실행 | 최종 unittest354개 통과·skip0. assets/경계31개는 계획/준비·출처·실패 보존·scoped fallback·malformed/timeout·순수 config·정확한 전역 제외/backup 예외·symlink·CLI 실패 검증. regression-final.txt | Docling/QMD 동작은 fake/mocked, Git 제외는 실제 Git을 임시 config/repo로 사용. 실자료/실제 CLI 미실행 |
| source 조립 | Codex·Claude 각각113개 파일, native_installable=false. 최종 source와 bundle bytes 일치·선택 제품 필수 링크 누락0개. 공통 Wiki 본문의 비선택 제품 조건부 링크1개는 해당 bundle에 파일을 포함하지 않으며 그 분기를 읽지 않는다. 원문40개 등록 catalog를 사용한 fresh 사전/사후 gate, pin 확인과 실제 payload Gitleaks | declared provider5개만 확인. 신규 Wiki/Mem 공식 설치 연결을 checkout으로 대체하지 않았으며 미연결은 미실행 |
| 실제 모델 | bmad-eval quality, 4사례×3회=12회, 세 독립 grader가 총48/48 항목 통과 판정. model-summary.json과 각 grading.json | 명시 kit fixture, workspace-write, ephemeral Codex exec, shared CODEX_HOME. baseline/variant·자연 발동·config-clean/압축·Claude/native/실 provider 성공 아님 |
| 기존 보호 기능 보존 | 기존 secret-hook source manifest와 현재 파일 hash 대조, 기존 시험 포함 회귀 | hash 일치는 기존 미실행/native 공백을 메우지 않음 |

새 세션 사례는 (1) 명시 project 단일 원본 검색·미색인 표시·추가 범위/쓰기 거부, (2) 승인한 두 빈 디렉터리의 계획→apply→실존, (3) 현재 회사 정책/작업 정본과 오래된 개인 NAS 경험 구분, (4) Wiki read-only provider 부재를 0건/완료로 오인하지 않고 갱신/설치/전송하지 않음이다. 각 supplied fixture127개 bytes 보존을 판정했다. 전체 호스트 무변경 증거로 확대하지 않는다.

기존 bundled records.py의 runtime doctor/worker/MCP launcher는 미이관이다. 공식 업무 entry로 연결한 것과 직접 대체 실행기가 없는 것을 구분했다. profile_config는 문법/필드·자료형·참조 검사이며 실제 sync/Git boundary resolver가 아니다. Git 제외 적용 실패의 여러 파일 원자성·동시 추출/색인의 보장은 없다.

모델 fixture 동결 뒤 CLI 고정 실패 진단·명시 scope의 기본 config 접근 생략·자체 bytecode 억제를 보완했고, 최종 직접 시험354개와 bundle에서 확인했다. 모델과 최종 source의 delta는 로컬 eval-source-delta.json으로 남긴다. 초기 조립 위치/bytecode 실패와 보완 기록·감사 발견은 로컬 audit.md, 최종 source hash는 verified-final/source-manifest.json을 참조한다.

### 2026-11-18 — 7번 Android·Wear OS source 이관

대상은 [7번 결정](decisions/20261118-migration-7.md)의 자체6개 연결·android-work 공통 경계·기존 bmad-build 조건부 연결이다. 실제 앱/SDK/기기/의존성 변경·실행·운영 설치/배포는 제외했다.

| 검증 층위 | 실제 결과·근거 | 한계 |
| --- | --- | --- |
| 형식·참조 | 공식 skill-creator quick_validate53개 통과, common/adapter source 상대 파일 링크 누락0개. 로컬 migration-7-20261118/format-links.json | 공식 resource closure·자연 발동/native 증거 아님 |
| 영향받는 직접 시험 | 조립26개·provider 선택13개, 합계39개 통과·skip0. assembly-tests.txt·provider-tests.txt | 실제 Android API 검증 아님. 이전 전체354개는 과거 근거이며 이번 수에 합산하지 않음 |
| source 조립 | Codex·Claude 각120파일, native_installable=false. 등록 원문46개 fresh 사전/사후 gate·기존 선언 provider5개 pin·실제 payload Gitleaks 통과. 최종 source와 양 bundle bytes 일치 | 신규 Android 공식 provider 미연결, checkout/구 kit 사본으로 대체하지 않음 |
| 기존 source 보존 | 6번 source hash 대조에서 기존 파일 중 bmad-build/SKILL.md만 변경. 실행/검사 엔진·tests 미변경 | 새 skill/공통 지침7개와 docs 추가. 운영 호환 인증 아님 |
| 실제 모델 | 최종4사례×3회=12회, 독립 grader3개가48/48 항목 충족 판정. 각 fixture138개 보존 | 명시 skill·synthetic 자료·workspace-write·shared CODEX_HOME. 실제 Android/native·자연 발동·config-clean 아님 |

새 세션 사례는 구조 범위, Wear/Compose pin과 별도 담당, 테스트 전략/runner 구성과 실행 구분, 기존 ADB 실패/partial/0건 결과다. 실제 지침·원자료 읽기와 resolver 수행, 자체 분석·공식 기능 부재·미실행의 구분을 확인했다. 초기12회는 첫 조회가 secret 훅에서 차단된 환경 실패로 업무 적용 미실행이다. exit0를 통과로 세지 않고 grading·실패 기록을 보존했다. 기존 검증 harness로 맞춘 pilot1회는4/4 quick look이며 최종12회와 합산하지 않는다. 내부 syscall 원인 확정은 아니다.

정적 감사는 동일 작성자의 역할/보존·구조/읽기·증거/완료3관점 대조, 모델 판정은 bmad-eval 공식 계약의 별도3개 grader가 run 번호별로 수행했다. 실제 로그/fixture·각 grading과 요약은 로컬 migration-7-20261118/model-summary.json, source hash는 verified-final/source-manifest.json에 남긴다. 모델 fixture와 최종 source의 일치도 별도 확인한다.

Wear 사례2회의 불필요한 fixture 안전 코드 읽기는 별도 개선점으로 기록했다. 이 시험은 baseline/variant·최적 읽기량/토큰 절감·실제 압축/재개·Claude/공식 provider 성공의 근거가 아니다. 추가 원문 참조 명령과 감사 문안의 설치본 heredoc 분류 오탐 후보·미실행 범위는 로컬 audit.md에 있다. 설치본/신뢰 변경·새 hook 수정/배포는 하지 않았다.

실제 SDK/API/기기/복원, 공식 설치본 필수 reference·제품 연결, 기존 미이관 실행기·private 기능·native 통합은 남아 있다. 공통 source 디렉토리 대조에서 구 skill-authoring은 plugin-authoring/skill 작성·감사 reference로 대체됐으며 이름 이관 완료를 전체 운영 기능 완료로 확대하지 않는다.

### 2026-11-18 — Private source 이관 연결 상태

private 구현은 별도 scratch tr-kit-private의 docs에서 관리한다. 자체9개 skill·역할/설정·개인 실행기를 새 구조로 이관했고 공통의 검증된 source-bundle-v1과 조립/검사 기능을 재사용한다. 공통에 개인 코드·설정·데이터를 추가하지 않았다. 이 후속 작업으로 common/base·adapters·scripts·tests의 소스는 변경하지 않았다.

private source와 native/실제 환경은 구분한다. 구3→신9파일 백업 설치 전환, 공통 Git guard 등록/chain/복구 관리기·artifact 예외 강제, 구 records 런처의 미이관 판단·공식 기능/native 통합·실제 세션 검증이 남아 있다. private의 상세 시험과 모델 실패/보완은 해당 private verification 정본에만 두고 여기 복제하지 않는다.

### 2026-11-18 — 전체 기능 이관 목록 대조

[전체 이관 현황](migration-status.md)에 기존 공통134파일·private60파일(합계194)의 책임 분류, dependency/자체 ID의59→53 표면 차이7개와 새 plugin-authoring, 새 private9개, helper/설치/CI의 미이관·대체·별도 계획을 기록했다. 숫자는 선언/자체 entry 비교이며 기능 수/실행 호환의 증명이 아니다. 소스 소유 범위·제외 범위와 권장 후속 G1~G7을 보고서에 명시했다.

이 목록 조사 단계에서는 source 파일 목록/내용·제품 선언/지원 코드·기존 검증 기록의 정적 대조와 문서 링크/증거 연결만 수행했다. 새로운 unit/모델/native/실호스트 시험을 했다고 집계하지 않는다. 조사 당시 직전 공통/개인 verified source manifest와 실행/skill/adapter/tests hash의 차이는0개였고 해당 코드·정책을 수정하지 않았다. 필수 고정 호스트 가드 외 별도 probe/배포·서비스/설치본·profile/인증·실자료 조회는 하지 않았다. Git guard 관리자·도구 준비/검증·정적 읽기량 측정·MCP/worker·native 포장/CI·백업 구 설치 전환이 기존 요약보다 상세히 드러났고 미구현을 검증 대기로 바꾸지 않았다. 이후 승인된 G1 변경은 다음 절에서 별도로 기록한다.

### 2026-11-18 G1: Git 등록·chain·복귀와 예외 강제

범위는 R-32 및 [G1 결정/구조](decisions/20261118-g1-git-enrollment.md)다. scratch source만 수정하고 임시 Git repo·로컬 bare remote에서 실행했다. 공식 Gitleaks 8.30.1의 기존 provision receipt·hash를 검증해 연결하며 새 설치/취득은 하지 않았다. 실제 사용한 Git은 2.43.0이다.

| 검증 | 실제 결과 | 판정 범위 |
| --- | --- | --- |
| G1 전용 직접 시험 | 최종24개 통과 | plan 무변경·CLI plan_id·bytes/mode 복귀·기존 hook 실패/인자/stdin·pre/post 검사·실제 commit/push·대체 index·공유/linked worktree·충돌·부분 쓰기 실패·예외/비밀 구분 |
| 공통 회귀 전체 | 378개 실행, 실패0·오류0·skip6 | 372개 성공. 환경변수로 실제 scanner 선택이 필요한6개는 이 회차에서 미실행. 아래 집중 회차로 분리 |
| 최종 관련 집중 회차 | G1 24개 + 실제 scanner6개, 합계30개 통과·skip0 | CLI 진단 보완 이후 현재 코드와 기존 Gitleaks 실제bytes·go.sum·오류/마스킹 시험. 두 회차를 더해 고유 시험 수를 늘리지 않음 |
| skill 형식/링크 | 공식 system skill-creator quick_validate 통과, 선택 skill/reference·docs의 끊긴 링크0 | 지원 metadata를 제거/변환하지 않고 검사. 역할·분기·본문/조건부 reference 정적 감사와 구분 |
| 자체 source 조립 | Codex·Claude 각122파일, fresh gate·정확 inventory·실제 비밀 검사 통과 | 양 bundle 모두 native_installable=false. 실제 제품 설치·trust·hook 활성 조합이 아님 |
| 새 Codex 세션 | 초기1회 실패 → 지침 보완 후 동일 명시 복합 요청의 새 세션1회 통과 | “staged 검사 + 등록 계획만, 파일 생성 금지”. 보완 후 필수 정책/임시쓰기 없는 검사는 미실행으로 보고하고 plan만 실행. state 미생성·apply 없음 |
| source 보존 | 기존 공통/private source194개와 새 private의 직전 verified51개 hash 변경0 | 기존 설치본/실자료를 전수 확인한 것이 아님. common 신규 변경은 별도 현재140파일 manifest로 보존 |

#### 실패와 보완 이력

- 설치된 구 PreToolUse hook이 `cat` heredoc의 자체 Python source 본문을 whole environment disclosure로 차단했다. 실제 환경 출력 명령은 실행하지 않았다. 가드/trust를 끄지 않고 파일 편집 도구로 작성했다. 새 source의 quoted cat 데이터 처리에 같은 자체 본문과 실제 후속 printenv 차단을 회귀 검증했다. 미확인인 임의 Python heredoc 전체 문제까지 해결했다고 확대하지 않는다.
- 최초 G1 19개 시험 중4개는 Git이 hook 출력을 stderr로 전달하는데 assertion이 stdout만 본 오류였다. 차단 코드는 관측됐고, 출력 결합을 고친 뒤 추가 경계 사례를 포함한24개로 검증했다. 정책/비밀 차단을 완화하지 않았다.
- 초기 조립 시험은 한 scope에 양 출력 artifact를 선언해 첫 Codex 조립 당시 아직 없는 Claude artifact 때문에 fresh transfer gate가 거부했다. 실패 출력은 보존하고 Codex는 단일 artifact scope·새 output으로 재검증했다. Claude는 별도로 통과했다. 통과를 위해 gate를 끄지 않았다.
- 첫 모델은 파일 생성 금지로 표준 index 검사기를 실행할 수 없자 직접 Gitleaks stdin 모드로 검사했다. 표준 검사 경로의 trusted config/정책 계약을 충족하지 않아 실패로 판정했다. 자동 등록/apply는 하지 않았다. 필수 정책·임시쓰기 부재 때 다른 scanner 모드로 대체하지 않고 해당 검사만 보류하는 지침을 보완했고 새 세션에서 확인했다. 모델 종료0을 준수 성공으로 계산하지 않았다.

#### 작성·감사와 읽기 범위

plugin-authoring의 kit/hook 저작·hook 감사, 변경한 security-scan의 skill 저작/감사, shared 구조·읽기/호출·행동 시험 기준과 공식 system skill-creator를 적용했다. 동일 작성자가 요구→코드/지침→시험을 대조한 것이며 독립 검수자가 감사한 것으로 보고하지 않는다. BMAD 공식 renderer는 해당 scratch/상위에 없었고 공식 build workflow는 미실행이다.

대표 Gitleaks 요청의 정적 읽기량은 이전 source bundle의 SKILL1370자+reference2829자=4199자에서 현재1460자+4712자=6172자로 증가했다. 등록/복귀 절차와 실패 경계를 추가한 결과이며 문자 수를 token/비용이나 실제 전체 모델 읽기량으로 변환하지 않는다. Semgrep/Trivy 요청에 이 reference를 기본 로드하지 않는다. 모델의 임의 source 재조회는 별도 관측이며 읽기 효율 최적화나 자연 발동을 검증한 것은 아니다.

검증 증거는 로컬 `_bmad-output/g1-git-enrollment-20261118/`의 direct-suite·final-focused 로그/JSON, 양 assembly 기록, 원형 보존 model/model-v2 events·request, reading-flow·source-manifest·verification-summary와 audit.md에 둔다. 모델 시험 repo는 실자료가 없는 격리 fixture다.

#### 남은 검증과 적용 경계

- 실제 운영 저장소 등록, Codex/Claude native hook/trust/활성 조합, Claude 모델·자연 발동·압축/재개·Windows 환경은 미실행이다. 현재 설치된 구 hook의 오탐이 이 작업으로 사라졌다고 하지 않는다.
- source 보호·Git 비밀/산출물·host role·사용자 승인·제품 권한은 서로 다른 경계다. 공유 hook runtime 의존 장애 시 미등록 worktree 영향, 원래 hook의 `$0` 의존, 동시 외부 쓰기와 전원 단절 복구는 한계로 남긴다.
- common source 변경에 따른 private의 엄격한 common pin 갱신·통합 재검증은 후속이다. private 검사를 끄거나 pin을 조용히 완화하지 않았다. G2~G7은 별도 남아 있으며 G1 완료를 전체 kit 적합·배포 완료로 해석하지 않는다.
- R-33의 PTBMAF/Design Doc·Obsidian 다기기 열람·NotebookLM CLI 논문 분석은 후속 고려사항으로 기록만 했다. 정확한 NotebookLM CLI 저장소·지원 조건은 미확인이다.

### 2026-11-18 G2: 공식 도구 준비·receipt·probe

R-34와 [G2 결정/구조](decisions/20261118-g2-toolchain.md)에 따른 scratch source 구현이다. 기존 자체 준비/검증 코드와 동일한 공식 manager/release 경로를 연결했다. 실제 새 package·browser·release 취득/설치·등록·shell 적용은 하지 않았다.

| 검사 | 관측 결과 | 범위/한계 |
| --- | --- | --- |
| G2 격리 시험 | 최종26개 통과·실패/오류/skip0 | 합성 archive·manager·browser/query/scan process protocol을 실제 자체 코드에 대조. 공식 runtime 취득/실제 semantic 실행 증명은 아님 |
| 공통 전체 회귀 | 402개 통과·실패/오류/skip0 | 실제 Gitleaks용 환경도 명시. 이 회차 뒤 G2의 dependency 분리·빈 version·stdin 처리와 probe 결과 검사를 최종 보완했고, 영향받은 G2 26개를 별도로 재검증. 현재 코드로 전체402를 다시 돌렸다고 합치지 않음 |
| Codex/Claude source 조립 | 각128파일, native_installable=false | 현재 source의 fresh 원문 gate·정확 inventory·실제 Gitleaks 검사. 실제 제품 설치/native 활성 조합은 미실행 |
| 새 Codex source 사용 | 최종 새 세션의 development·Gitleaks plan 모두 종료0, prefix 생성 없음 | 명시한 “설치 없이 두 계획만” 요청에서 버전/hash 확인과 실제 실행을 구분. apply·다운로드·환경 적용 없음. 자연 발동·Claude·압축 검증은 아님 |
| 형식·연결 | security-scan 공식 quick_validate 통과, 새 guide/CLI와 docs 참조 대조 | 본문 원문 변환 없이 검사. role/조건부 읽기·설치 경계를 동일 작성자가 감사 |

실제 격리 사례는 신규/기존/source 내부 prefix·plan 및 prerequisite/pin drift·checksum 실패·symlink archive/escape·engine/Python package·실행 version·빈 version·잘못된 receipt inventory·독립 Gitleaks pin·안전한 shell 인용·부분 설치 실패/명시 새 prefix 회복·Semgrep parse 오류·다른 patch version·네트워크 기본 비활성·자기 browser session timeout/cleanup을 포함한다. Gitleaks receipt는 기존 공통 verify_scanner와 test용 pin 계약으로 대조했다. 가짜 archive checksum을 공식 배포의 검증 실적으로 계산하지 않는다.

#### 보존·정정·검수

- 새 helper·세 CLI·공통 guide와 관련 pin/reference를 작성했다. 실제 prefix·기존 설치본·profile·provider·hook·서비스는 변경하지 않았다. private의 source/pin도 자동 변경하지 않았다.
- 기존 선택한 CLI/engine/Semgrep/Trivy/Gitleaks 버전은 유지했다. 기존 준비기의 Node 최소22.13.0·Python Playwright1.64.1을 명시했고 현재 자체 runner의 Python3.11 전제를 분리했다. runtime 업그레이드는 미실행이다.
- status의 필수 artifact 목록과 저장 pin 내용 대조, 빈 version 및 Gitleaks-only의 불필요한 development 의존을 보완했다. 새 계획도 실제 버전 명령이나 설치 성공을 뜻하지 않는다.
- 최초 source 목록의 “security-tools에도 Gitleaks pin 중복”은 파일 개별 대조에서 잘못된 판독으로 확인돼 정정했다. 실제 pin은 secret-tools에만 있었다. 존재하지 않은 중복 제거를 완료 실적으로 세지 않는다.
- 첫 새 세션 시험도 설치 없이 plan만 수행했으나 이후 코드 보완으로 implementation hash가 달라졌다. 원형 증거를 보존하고, 최종 새 세션을 다시 실행해 입력 source snapshot 변경0·새 prefix 생성0을 확인했다. 첫 결과를 최신 revision의 시험으로 재사용하지 않는다.
- 실패 prefix는 보존하고 새 prefix로 계획하는 회복만 구현했다. 같은 prefix resume/자동 삭제·기존 설치 채택·운영 연결 전환을 완료로 표시하지 않는다. 외부 전체 runtime closure·서명과 OS/네트워크 격리는 별도 한계다.
- 구 검증기의 bundled diagram self-check/export 호출은 새 source에 가져오지 않았다. 공식 provider/resources와 연결할 검증은 G7에 남기며 브라우저 smoke로 완료 처리하지 않는다.

plugin-authoring의 kit 작성·skill/reference 저작·감사·shared 구조/읽기/행동 시험과 공식 system skill-creator를 적용한 동일 작성자 검수다. 실제 BMAD build renderer/workflow를 실행했다고 보고하지 않는다. 상세 기준을 docs에 복제하지 않고 common/base/references/toolchain.md로 연결한다. Semgrep/Gitleaks 일반 검사는 이 guide를 자동 로드/설치하지 않고 명시 도구 준비 요청에서만 선택한다.

로컬 증거는 `_bmad-output/g2-toolchain-20261118/`의 direct-suite·final-focused, 양 제품 assembly, model/model-v2 원형 로그·입력/source snapshot, source manifest·감사·검증 요약에 둔다. 현재 작성된 source/임시 protocol과 실제 새 기기에서의 공식 취득·브라우저·검색·스캔 성공을 분리한다. 실제 설치/취득, network query/CVE DB, Claude/native/운영·private pin 갱신은 후속 통합 검증이다.

### 2026-11-18 G3: 선언 읽기량 측정기

R-35와 [G3 기록](decisions/20261118-g3-context-check.md)에 따라 기존 자체 측정기를 common/base 로직·루트 CLI·새 source cases로 이관하고 shared/reading-flow에 연결했다. 실제 모델 읽기 수집/hook·tokenizer·자동 축약·운영 설치/배포는 추가하지 않았다.

| 검증 | 결과 | 관측 범위 |
| --- | --- | --- |
| 전용 직접 시험 | 26개 통과 | 기존5개 동작·full SKILL·절/metadata·CRLF/Unicode·겹침/alias·symlink 밖 거부·원문 변경·미측정·schema·dependency 부재·CLI 결과 구분 |
| 관련 회귀 | 전용26개와 source 조립26개, 합계52개 통과·skip0 | 전체 kit의 수백 개 시험을 새로 실행한 것으로 합산하지 않음 |
| 실제 source cases | 5개 측정 성공, metadata 양쪽53개/5249자 | 저작 기준 선택 경로14888→17153자(+2265), 나머지4개는 동일. 미측정 외부/동적/업무 자료가 있어 전체 컨텍스트 비용이 아님 |
| 기존 비증가 비교 | exit1, passed=false | 측정 자체는 성공. 새 안내 증가를 숨기거나 allowance를 넣어 통과시키지 않음. 명시 measure-only는 exit0이며 비교 판정 미요청 |
| source 조립 | Codex·Claude 각131파일, fresh gate·정확 inventory·Gitleaks 통과 | native_installable=false, 실제 설치/제품 활성 조합은 미실행 |
| 새 Codex 명시 사용 | 독립 A/B1회, fixture/source hash 변경0 | A 정상 측정·부분 겹침·metadata 구분. B의 after 파일 부재를 exit2/미확인으로 보고하고0자로 계산하지 않음 |
| 형식/연결 | 공식 system skill-creator quick_validate 통과·끊긴 링크0 | 같은 작성자의 kit/skill·shared 기준 대조. 독립 감사·자연 발동·Claude·압축 시험은 아님 |

초기 전용26개 중 multiline YAML description의 마지막 개행을1자 적게 센 사례1개가 실패했다. frontmatter 추출이 YAML block scalar의 마지막 개행을 버린 원인을 수정하고 해당 사례와 전체 전용/관련 회귀를 재검증했다. source 본문과 YAML 해석값의 문자 단위를 분리하고 원문 snippet을 오류에 출력하지 않는다.

새 세션 A의 선언 읽기 합계는170→232(+62), 겹친 재독47→78(+31), 중복 제외123→154(+31), metadata11→11이었다. B는 선언 파일 부재로 비교 수치를 확보하지 못했다. 실제 tool 실행/결과와 최종 답을 대조했고, 모델 종료0만으로 성공 판정하지 않았다. 명시 지침 사용 한 번을 임의 요청의 자연 선택·전체 실제 읽기/token 비용·실제 압축 보존으로 확대하지 않는다.

case JSON은 부분 경로 예제이며 필요한 전제·입력·외부 절차의 누락 여부를 도구가 자동 감사한 것이 아니다. canonical 동일 파일 구간의 재독만 측정하고 cross-file 의미 중복은 판단하지 않는다. ATX/fence 부분 파서이며 완전한 Markdown 렌더/parser 검증이나 전체 source tree의 원자적 snapshot은 아니다. 실제 새 배포의 Python/PyYAML 전제·native 경로 연결과 private common pin은 후속 통합 대상이다.

증거는 로컬 `_bmad-output/g3-context-20261118/`의 direct-focused/final-focused·measure-only/legacy-comparison·source-cases-summary·assembly·model 원형/request/source/fixture snapshot·현재 source-manifest·audit에 둔다. source151파일은 해당 측정기/시험 변경을 포함한 범위이고, 기존 source/private·호스트 설치본을 변경한 것으로 해석하지 않는다.

raw 목록/hash·파일별 책임 분류·선언/새 entry 대응은 로컬 _bmad-output/migration-inventory-20261118에 남긴다. source 대조와 기록 완료를 kit 전체 요구 원문 감사·전체 적합·운영 준비 완료로 확대하지 않는다. 방법론 신규 계획과 사용자가 스킵한 Obsidian을 기존 이관 기능의 삭제/자동 신규 도입으로 분류하지 않았다.

### 2026-11-18 G4: Claude-Mem 실행기 연결

R-36과 [G4 기록](decisions/20261118-g4-claude-mem.md)에 따라 외부 공식15.2.1 entry용 공통 연결·수명/health 코드와 제품별 설정 fragment를 작성했다. 구 bundled engine·검색 proxy·원문 치환을 가져오지 않았다. source 기준과 호스트의 실제 공식 설치·동작을 구분한다.

| 검증 | 결과 | 관측 범위·한계 |
| --- | --- | --- |
| 전용 직접 시험 | 25개 통과, 실패/오류/skip0 | 합성 worker HTTP·stdio 서버·runtime shim을 실제 자체 CLI/helper로 실행. 공식 서버/DB의 검색 정확도나 runtime 호환성 증명은 아님 |
| 관련 회귀 | provider13개·source 조립27개 통과, 전용 포함65개 | 제품별 MCP `.in` 경로 보존과 native config 자동 생성 부재 포함. 전체 kit 수백 개 검사를 이번 결과로 합산하지 않음 |
| worker 경계 | 준비/중단·중복 시작·degraded·timeout·exit0 미중단·PID 시작 tick/command drift·외부 listener 거부 통과 | Linux 합성 프로세스. 공식 daemon supervision·PID 변경/자식 process와 실제 queue/AI/Chroma 동작은 미실행 |
| stdio 경계 | initialize·알림·tools/list·합성 project A/B 조회, cwd 유지·autostart false·worker 미기동 통과 | 테스트 더블의 합성 결과이며 실제 개인 기록을 조회하지 않음. 제품 native tool discovery/권한 검증은 미실행 |
| source 조립 | Codex·Claude 각136파일, fresh 원문 gate·정확 inventory·실제 Gitleaks 통과 | native_installable=false. MCP 등록·활성화나 plugin 설치/배포 완료가 아님 |
| 새 Codex 명시 사용 | plan·doctor·양 제품 render,4명령 exit0 | 도구 실행/최종 보고 대조. static entry-pinned와 실제 검색/준비 미검증을 구분. fixture7파일 hash 변경0, data/state 생성0 |
| 형식·연결 | 공식 system skill-creator quick_validate로 mem-search/document 통과, 변경 안내 상대 링크 오류0 | 동일 작성자의 역할·조건부 읽기·외부 원문 금지·요구 대조. 독립 감사나 자연 발동·Claude·압축 시험은 아님 |
| source 보존 | 기존 공통134파일·기존 private60파일·새 private51파일 변경0 | 각 기존 source manifest의 범위. 호스트 전체 파일·설치본 상태를 조회/인증한 것이 아님. 새 공통158파일 manifest 보관 |

초기21개 시험 중 기동 관련5 error·1 failure가 발생했다. 새로 생성한 launcher가 interpreter로 exec하면서 command hash가 바뀌어 같은 PID의 정상 기동을 소유 실패로 보던 원인이었다. 같은 PID/시작 tick에 한해 준비 중 최종 command를 기록하도록 보완해21개를 재검증했고, 이어 symlink write·불일치 health·실패 child·MCP stderr 경계를 추가한 최종25개를 통과했다. running 이후 identity drift를 자동 수용하는 방식으로 완화하지 않았다. 생성 중 identity 부재도 launch PID/log와 실패 상태를 남기며 성공으로 보고하지 않는다.

신규 모델 시험은 별도 source 밖의 합성 provider fixture를 사용했다. 최초 시험 준비 스크립트가 source 내부에 fixture를 생성한 배치 오류는 실제 모델 실행 전에 고쳤다. source 내부 파일을 provider로 인증하거나 예외로 허용하지 않았다. 최종 모델은 안내 조회·역할 가드·plan/doctor/render만 수행했고 start/stop/mcp/health·설정 저장·실자료·네트워크 작업은 도구 trace에 없다. 이 명시 사용1회를 임의 요청의 자연 선택·모든 실패/모호함·제품 native 준수로 일반화하지 않는다. source 전후 hash를 모델 시험 전후로 별도 취득하지 않았으므로 모델이 source를 전혀 바꾸지 않았다는 독립 filesystem 실측 주장도 하지 않는다.

기존 개인 DB/state의 자동 채택·이관은 지원하지 않는다. start는 실제 DB 초기화/이전·queue/background/의존 접근을 일으킬 수 있으며 marker·receipt는 OS 권한 격리나 공식 provenance 인증이 아니다. port 사전 확인/기동의 경쟁과 upstream process handoff는 실환경 후속 검증 대상이다. native config 적용·공식 runtime/resource 취득/실행·개인 query/save/capture·기존 worker 제어·원격 전송/운영 적용·private common pin 갱신은 미실행이다.

로컬 `_bmad-output/g4-claude-mem-20261118/`에 direct/providers/assembly-tests-final 로그·실제 source 조립 기록·source manifest와 G3 대비 변경 목록·기존 파일 보존 대조·model request/events/fixture 전후 hash·동일 작성자 감사 기록을 남겼다. 실제 공식 설치 출처·전체 resource·양 제품 활성 조합은 G5/G7에서 별도 증거로 판정한다.

### 2026-11-18 G5: 공통 native 패키징·격리 lifecycle·검사 전용 CI

R-37과 [G5 결정](decisions/20261118-g5-packaging.md)에 따라 기존 source 조립기의 fresh 원문·inventory/Gitleaks gate를 유지하면서 자체 native metadata·초기 지침 전달·공식 manager 연결을 추가했다. 운영 common/private 설치본·신뢰 DB·개인 자료·worker/timer·원격 Git은 변경하지 않았다. 이번 실제 제품 시험 대상은 별도 prefix의 Codex CLI0.167.2다.

| 검증 | 결과 | 범위와 한계 |
| --- | --- | --- |
| 전용 source 시험 | 최종24개 통과·실패/오류/skip0 | 양 제품 metadata/경로·review/guarded·조합·원문/metadata drift·symlink·실패·정적 plan/apply 검사·복귀·remove exit0/cache 잔존 등. native manager는 이 단위 시험에서 double 사용 |
| 전체 로컬 CI | 중간 source475개 통과·skip0 | 실제 pinned Gitleaks 명시. 이 실행 이후 renderer 재사용·log 보존·malformed JSON·제거 관측·정적 plan/implementation hash를 보완하고 최종 전용24개 재검증. 현재 source 전체를 다시 돌렸다고 표시하지 않음 |
| 최종 native 후보 | 양 제품 review/guarded 및 Codex update용 합계5개, 각151파일 | fresh 원문·현재 inventory·실제 Gitleaks 통과. source inventory와 최종 코드 일치. profile/version별 별도 출력. operational_ready=false |
| source-bundle-v1 보존 | Codex·Claude 각147파일, native_installable=false | native 분기와 별도 raw source interface도 fresh 조립/검사. private pin을 자동 갱신하거나 통합 성공으로 처리하지 않음 |
| Codex 실제 manager | 최종 후보 install→update→rollback→remove 성공 | 매 단계 별도 home/config/cache, 설치본 payload byte 대조·제거 후 대상 cache 부재. 이전 package 보존. hook trust·초기 event·모델 native skill 발견은 이 시험으로 검증하지 않음 |
| 실제 package 내부 실행기 | 양 제품 context 출력·정상 upstream binding4사례 통과 | compact 합성 입력에서 원칙 본문 누락0, 출력1739/1743자. 조회 비간섭·등록 원문 복사 Pre deny 확인. 실제 source 쓰기/원문 복사는 수행하지 않았고 native event 시험은 아님 |
| 전송 후보 검사 | 정확한 hash exit0, 다른 hash exit2, pushed=false | 현재 package·fresh 원문/실제 Gitleaks 재검사. 원격 clone/commit/push·게시 없음 |
| 신규 CI 정의 | YAML 파싱·PR/수동 trigger·contents:read 확인 | key/SSH·push trigger·배포/업로드 job 없음. runner temporary에 pinned scanner 준비. 실제 GitHub workflow는 미실행 |
| 새 Codex 계획 사용 | 최초 범위 충돌 발견, 보완 후 실제 plan exit0 | 동일 계획 전용 조건 유지. apply/native CLI·scanner 실행 없이 계획을 출력, prefix 생성0. 회사 PC 준비를 검증 완료로 확대하지 않음 |
| source 보존 | 기존 common134·기존 private60·새 private51 변경0 | 기존 manifest 범위. 새 common172파일 manifest와 G4 대비 추가14/기존1 변경 보관. 전체 호스트 파일 불변을 실측한 것은 아님 |

#### 발견과 보완

- 최초19개 전용 시험 및 실제 Codex4단계 후 검수에서 renderer 자체 검증 재사용·로그의 단계별 보존·isolated config symlink 거부·제거 후 cache 관측을 보강했다. 이전 출력을 덮어쓰지 않고 새 후보로 재조립/재시험했다. 이전 실적을 최종 byte의 시험으로 잘못 재사용하지 않는다.
- 잘못된 native JSON `[]/null/true/string`이 object 접근 오류로 끝나는 회귀 사례는 초기4개 subcase 모두 실패했다. JSON object를 먼저 확인하고 Pre에서 명시 deny를 반환하도록 수정해 최종 시험을 통과했다. 제품이 interpreter 오류를 자동으로 안전 차단한다고 가정하지 않았다.
- 첫 새 세션은 계획 함수도 scanner receipt를 읽고 임시 scan 파일을 만드는 점 때문에 지정한 조회/무쓰기 범위로 수행할 수 없다고 보고했다. 정적 plan은 파일/hash만 읽고, 실제 apply는 prefix 생성 이전 필수 scanner를 수행하도록 분리했다. scanner 부재 시 plan은 가능하지만 apply는 쓰기 전에 실패하는 회귀 사례를 추가했다. 기준을 낮춘 검사 통과로 기록하지 않는다.
- 보완 후 새 모델은 안내/CLI 인자 조회와 실제 계획 출력을 수행했다. 도구 trace에서 --apply/native manager/네트워크/파일 저장은 없고 계획용 prefix도 생성되지 않았다. manifest·CLI·receipt·구현/검증 코드 hash와 검사 미실행 상태를 보고했다. 명시 안내 사용 사례를 자연 발동·실제 압축·native 초기 주입 검증으로 확대하지 않는다.

#### 미실행·제한

Claude CLI는 현재 PATH에서 찾지 못해 실제 validate/install/update/uninstall·callback 시험은 미실행이다. 공식 문서 형식·합성 제품별 handler/command·직접 packaged script 검사와 구분한다. Codex도 trust 승인·실제 SessionStart 수신·압축 후 수신·native guard 조합/차단·공식 providers/MCP 업무 실행은 미실행이다. raw hook JSON·설치 목록만으로 초기 주입/강제 보호 완료를 판정하지 않는다.

native 시험은 실자료 없는 별도 임시 prefix에서 했다. 운영 데이터·plugin persistent data·기존 세션의 복원/유지나 임의 partial 상태의 자동 복구까지 검증하지 않았다. partial은 실패 단계/로그를 보존하고 무조건 재전송을 거부하며, 관측 후 별도 수습 계획이 필요하다. receipt와 self-declared inventory는 서명·공식 provenance·OS 원자적 격리가 아니다.

기존 Apache LICENSE·과거 own 저작 lineage를 보존하고 없는 외부 동봉을 고지하지 않도록 정리했다. 외부 공식 설치본의 개별 사용·배포 조건/resources·제품 지원과 private common pin/native 연결은 G7·후속 통합 대상이다. 원격 전송/운영 적용·전체 README 재작성은 미실행이다.

실제 적용 기준은 plugin-authoring의 kit·hook 작성/감사와 shared 구조·읽기/행동 기준, 공식 제품 문서와 기존 자체 scanner/renderer다. 이 단계에 신규 skill은 없으며 공식 skill-creator의 신규 skill 생성 workflow나 BMAD build renderer를 실행했다고 보고하지 않는다. 동일 작성자 대조와 별도 모델 사용 시험을 독립 전문 감사로 표시하지 않는다.

증거는 로컬 `_bmad-output/g5-packaging-20261118/`의 direct/static-plan-focused·malformed-before·packages-candidate/build-candidate·native-cycle-candidate·packaged-context/guard·delivery-check·source-bundles·model/model2 원형·source manifest/변경/보존·workflow·audit에 둔다. 전체 CI 원형은 `/data/projects/_scratch/tr-kit-g5-ci-20261118/`에 있고 기존 실패/중간 결과도 보존했다.

### G7 설치본 검수 연결 — 2026-11-18

- 적용 기준: own plugin-authoring의 kit/skill·조건부 shared 기준과 공식 system skill-creator의 기존 저작 기준을 재사용했다. 새로운 외부 저작 workflow를 실행했다거나 동일 작성자 대조를 독립 감사로 표시하지 않는다. 실제 BMAD 공식 설치와 렌더 수행은 미실행이다.
- 공통 전체500개 시험이 통과했다. 이후 검수 파일 부재가 소유 worker의 새 stop 계획을 막는 사례를 보완하고 최종 memory30개·provider29개를 다시 통과했다. 변경 뒤 전체501개를 재실행했다고 합산하지 않는다. private는 최종150파일 common pin으로 전체106개가 통과했다. 실제 scanner를 사용하는 기존 회귀를 포함하며 합성 worker·systemctl fixture와 운영 실행을 구분한다.
- provider 전용16개는 pending/미결/미지원·다른 제품·선택하지 않은 부재·entry repin·리소스 추가/누락/변형·설치 근거 변동·symlink/크기·업데이트 차이·오류 출력 등을 확인했다. 기존 route13개를 포함한29개다. 원문 내용 유사성/출처 서명·관리자 공격·OS 격리를 검증한 것이 아니다.
- Claude-Mem은 구 schema1 정적 확인 유지/새 실행 거부, schema2 검수 변경·리소스 drift의 실행 전 거부, 검수 기록 변동/부재 후 소유 worker stop과 기존 lifecycle/readiness/stdio 회귀를 확인했다. 실제 공식15.2.1 서버나 개인 DB에는 연결하지 않았다.
- 기존 실제 npm 설치의 Context7 0.8.2·Playwright CLI 0.1.22 metadata/lock/공식 archive SRI를 대조했다. 메모리 안에서 archive 각 file hash를 비교했고 설치본10/16파일이 모두 일치했다. archive/원문은 kit에 저장하지 않았다. 전이 의존과 native/runtime 미검증 때문에 두 snapshot은 pending이다.
- 새 Codex0.167.2 명시 호출 시험에서 pending·resource drift 두 사례를 각각 CLI로 검사했다. entry 성공/검수 실패를 구분했고 새 snapshot을 stdout으로 대조한 뒤 미실행/미결을 보고했다. fixture10파일 hash가 동일했다. 직접 지시한 source 시험이며 자연 발동·Claude·native hook·공식 workflow·실제 압축/재개 통과로 확대하지 않는다.
- fresh source 조립은 Codex/Claude150파일 각각, private48파일 각각 통과했다. 공통 native review/guarded × 두 제품4개 후보는154파일씩 생성/실제 파일 명세·source/원문 보호·fresh 비밀 검사 통과. `operational_ready=false` 유지, 설치·trust/이벤트 실행은 하지 않았다. private는 source-bundle이며 native 패키지가 아니다.
- 선언한 reference 읽기량3경로를 G5 기준과 measure-only로 대조했다. metadata는53개/5249문자로 동일하다. 연결 조사도 새 필수 안내 때문에260문자 증가했고 실제 수행의 검수 reference는 추가 읽기다. 증가를 비용 절감이나 통과 기준 변경으로 숨기지 않는다. 외부 지침·실행 출력/실제 주입·전체 모델 읽기는 미측정이다.

남은 것은 공식 설치/관리 근거가 아직 없는 provider들의 준비와 필수 외부 closure·선택 버전/ABI, 실제 Codex/Claude workflow와 trust/callback·공통+private native 조합·REA·기존 개인 데이터 전환·실제 압축/재개다. G7 전체 실환경 검증 완료가 아니라 **G7 source 보완·격리 검수 완료**로 기록한다. 운영 설치·설정·자료·백업/timer·공유/배포·commit/push는 실행하지 않았다.

로컬 증거: `_bmad-output/g7-provider-review-20261118/`의 baseline·common-tests·memory/provider-final-tests·npm 관측·pending snapshots·common pin 차이·source/native 조립·model 요청/원형/summary·reading measure·audit·최종 manifest. private 증거는 별도 private scratch `_bmad-output/g7-provider-integration-20261118/`에 있다.

### 2026-11-20 후속1번: 실제 공식 준비·호출

고정 commit의 요청 skill42개씩 중 metadata3개를 포함한41개씩을 공식 설치했다. retrospective는 공식 YAML 구문 오류로 누락됐다. 8개 source family의 archive 대조에서 설치된82개 skill 폴더 원문이 일치했다. 공식 native Wiki32/54파일·Claude-Mem198파일씩도 manager의 고정 source와 일치했다. 제품별46개 호출 entry와 명시 검수92개가 fresh 검사에 통과했다. 검수 일치를 native 발동·전 workflow·공급망 인증으로 해석하지 않는다.

own G2 준비기를 실제 실행해 기존 pin의 npm/uv/release/browser 설치·버전·receipt를 확인했다. Semgrep 탐지/정상, 실제 Python/CLI Chromium click·격리·screenshot·자기 session/server cleanup, 공개 Context7 정확 버전 docs와 Trivy 실제 DB 합성 검사를 통과했다. 초기에 probe Python quoting·긴 socket path·file URL 제한 때문에 실패했고, own 검증기 수정/짧은 새 evidence/문서 하나의 loopback 서버로 대조했다. 원문/runtime·브라우저 보안 설정을 바꾸지 않았다. 각 실패 로그도 보존했다.

공식 BMAD setup/help/build renderer·Archify doctor/demo·Wiki CLI/session status를 실제 실행했다. CLI 존재/리소스와 전체 agent workflow 수행은 구분한다. 실제 공식 Claude-Mem15.2.1 stdio initialize/19개 tool 노출·빈 합성 project search·worker readiness·소유 stop을 확인했다. 첫 worker는 CLI 부재로 degraded였으며, own binding의 선택 claude_bin을 보완해 새 data/state에서 ready+stop을 확인했다. 기존 개인 DB·대화·observer AI 작업·인증은 사용하지 않았다.

독립 Codex 명시 호출5사례는 원문 README, Diagram Design, doc-coauthoring의 Context Gathering, Android architecture 설계 검토, Wiki read-only 조회다. 실제 command/output을 대조했고 README/차트의 공식 검증과 Wiki fixture3파일의 hash 보존을 확인했다. Claude 모델·자연 발동·전체 hook·실제 SDK/기기·압축/재개는 미실행이다. README probe의 선택 Markdown linter는 없었고 로컬 구조/예제 검사 범위로 보고했다. 사용자 kit README를 재작성한 것이 아니다.

수정 source 전체504개와 관련 memory33개/toolchain26개 시험이 통과했다. 다만 새 source 조립은 Sites1.1.6 대조 파일/선언 경로 소실 때문에 fresh gate unavailable로 보류됐다. 현재1.1.7은 다른 hash이며 이전 원문과 의미 비교는 미확인이다. 기존 catalog를 삭제·완화하거나 새 bundle/private pin을 완료로 올리지 않았다. 실제 synthetic Python heredoc set(...)의 whole-environment 오탐은 새 classifier에도 남아 있음을 확인해 후속 보완 대상으로 기록했다.

실행/오류/미검증/조립 보류의 상세와 로컬 증거 위치는 [1번 결정 기록](decisions/20261120-official-provider-validation.md)에 있다. 운영 설치/신뢰·원격 전송·개인 자료 수집·commit/push는 하지 않았다.

#### 공식 원문 채택 승인 후 재조립

후속 사용자 확인으로 현재 공식 Sites1.1.7 원문을 대조 기준으로 채택했다. 이전 목록/초안과 hash를 보존했고, 현재 검사기의 schema2로46개 원문 metadata를 다시 확인했다. source 코드·검사기·보호 범위는 변경하지 않았다. 기존1.1.6 원문이 없어 두 원문의 의미 차이는 미확인으로 유지한다.

공통 source Codex/Claude150파일씩·private source48파일씩의 fresh source/원문 보호·전송·비밀 검사와 실제 파일 명세 대조를 통과했다. 공통 조립 회귀27개와 새 공통 exact pin을 선택한 private 전체106개가 통과했다. 이전150파일 G7 공통 묶음도 새 pin에서는 양 제품 모두 거부됨을 확인했고, 역할 정책 bytes는 유지됐다. 현재 common/base·adapters·scripts·tests의 코드가 앞서 전체504개 시험 당시와 같음을 hash로 확인했으므로 그 근거를 재사용한다. 전체504개를 이번에 다시 실행한 것으로 보고하지 않는다.

원형은 `_bmad-output/official-provider-validation-20261120/`의 catalog-adoption·source-*-official·new-common-pins·common-pin-diff-adoption·adoption-assembly-tests, private scratch의 `_bmad-output/official-catalog-adoption-20261120/`의 inputs·assembly·private-tests·pin-checks다. source 재조립 보류는 해소됐고 native 설치/신뢰/호스트 전환·남은 hook/원문 문제는 별도다.
