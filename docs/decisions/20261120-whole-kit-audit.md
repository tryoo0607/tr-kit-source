# 공통·private 전체 kit 감사

## 결과와 범위

2026-11-20 사용자가 직전의 ‘발견 사항을 포함한 전체 kit 감사’에 “ㄱㄱ”로 진행을 요청했다. **감사와 격리 재검사는 완료했으나 전체 운영 적합 판정은 보류한다.** 아래 연결 누락·작업 폴더 상태·보고 오류·기록 충돌을 남겼다. 발견 사항을 자동 수정하거나 운영 설치·배포하지 않았다.

후속1번 승인 뒤 A-02는 source 수정·직접/모델 검수를 진행했다. 정본은 개인 scratch의 `docs/decisions/20261120-native-format-routing.md`, 현재 요약은 [verification.md](../verification.md)다. 아래 발견/실패 표는 감사 시점 기록으로 보존하며, 새 private 패키지 설치·native 수집이나 다른 발견의 해결까지 뜻하지 않는다.

후속2번 승인 뒤 A-01의 캐시2개를 보존·제거하고 **원래 공통 폴더의516개 회귀와 양 제품 source 조립**을 통과했다. 상세는 아래 ‘A-01 후속 정리’ 절이다. 초기 실패는 당시 증거로 보존한다.

대상은 `/data/projects/_scratch/tr-kit-source`와 대응 private scratch다. Git HEAD가 양쪽 모두 없어 실제 파일 hash를 기준으로 삼았다. 공통205파일·private70파일을 명시 목록으로 고정했고, 공통의 기존 bytecode2개는 별도로 기록·보존했다. 81개 Python 파일의 문법, 자체 skill62개(공통53/private9)의 metadata·형식·목차·로컬 링크, 전체 구성 간 의존과 중요 실행 경로를 대조했다.

적용 기준은 [plugin-authoring](../../common/base/skills/plugin-authoring/SKILL.md)의 kit/skill/hook 감사, 각 작성 기준과 조건부 구조·읽기·행동 시험 reference다. 기존 조립·CI·provider 검수·원문 보호·공식 Gitleaks8.30.1·공식 skill-creator 형식 validator를 재사용했다. validator 사용을 skill-creator의 전체 저작 절차 수행으로 표현하지 않는다. 동일 작성자의 감사이며 독립 전문 감사나 별도 모델의 전수 검수는 아니다.

이번에는 원격 작업·제품 설치·실제 서버 조회를 새로 수행하지 않았다. 기존 native·MCP·실제 모델 시험은 아래 범위와 현재 파일의 유효성을 확인해 제한적으로 재사용했다. 모든62개 skill의 모든 의미·분기·모델 행동을 새로 실행했다고 주장하지 않는다.

## 발견 사항

| ID·우선순위 | 관측과 영향 | 보완 제안·재검증 |
| --- | --- | --- |
| A-01 · 조립 전 처리 | 현재 공통 `common/base/scripts/__pycache__/upstream_guard.cpython-312.pyc`, `scripts/__pycache__/plugin-lifecycle.cpython-312.pyc`가 존재한다. [조립기](../../scripts/assemble.py)는 bytecode를 source 입력으로 거부하며 양 제품 inventory 호출이 실패했다. 원래 폴더 회귀516개도 errors20/failure1이다. errors20은 bytecode 거부, failure1은 기대한 partial 산출물 부재다 | 파일의 생성 주체는 미확인이다. 소유·보존 필요를 확인해 정리하거나 승인된 깨끗한 source 입력을 준비하고 원래 대상에서 재검사한다. 이번에는 삭제하지 않았다. bytecode를 제외한 별도 검사용 사본은 나머지 모든 파일의 hash가 같고516개가 통과했다 |
| A-02 · native 기능 연결 보완 | private의 `wiki-capture.py:113`은 `common_links.skill(..., 'wiki')`에서 설정의 `common_format`을 전달하지 않는다. 기본값 source 때문에 정상 native root의 assembly.json을 찾다 실패한다. `personal-library/SKILL.md:24`의 document 연결 명령도 `--format`을 생략한다. helper가 형식을 추측하지 않는 계약과 호출부가 어긋난다 | 확인한 설정의 명시 source/native를 두 호출부에 전달한다. source 기본값과 pin 검사는 유지한다. native/source 정상·형식 불일치·공통 부재·비활성 무부작용을 재시험하고 개인 skill 감사·패키징을 다시 수행한다. 형식 자동 탐색·pin 완화로 해결하지 않는다 |
| A-03 · 보고 신뢰성 보완 | [직전 실제 모델 시험](20261120-real-work-compaction-validation.md)에서 Claude가 허용된 `-B` 명령을 허용 표기와 다르다고 설명하고, 실제 환경을 확인하지 않은 캐시 생성 전제와 불필요한 재확인을 덧붙였다. 기존 시작 실패 응답의 근거 없는 원인 가능성 추정도 미교정이다 | 설명에 쓴 명령·권한·환경의 근거를 실제 관측과 대조하는 절차와 모델 시험이 필요하다. 모르면 미확인으로 남겨야 한다. 제약 문구가 존재하거나 이번 합성 분석 표가 맞았다는 이유로 이 문제의 해결을 선언하지 않는다 |
| A-04 · 현재 상태와 이력 구분 | [architecture.md](../architecture.md)는 첫 절에서 native 재사용 인터페이스를 설명하지만9행에는 private native 계약/패키징을 미결이라고 적고 있다. ‘아직 정하지 않은 부분’과 R-02/R-06/R-12 등 요구 행에도 초기 미구현/미실행 상태가 남아 있다. 상단 검증 이력만으로 모든 위치의 현재/과거 판별이 명확하지 않다 | 상세 과거 결과는 보존하고 현재 상태 표·이력 표기·최신 근거 링크를 정렬한다. 감사 보고 추가를 기존 전체 상태 문서의 교정 완료로 세지 않는다 |
| A-05 · 낮은 우선순위 형식 | private artifact-backup은 `실패와 복구` 뒤에 `결과와 완료 판단`을 둔다. 자체 [목차 규격](../../common/base/skills/plugin-authoring/references/skill/authoring.md)의 순서와 다르다. 공식 validator는 이 kit 고유 목차 순서를 검사하지 않으므로62개 형식 통과와 양립한다 | 내용을 삭제·축약하지 않고 절 순서만 정렬한 뒤 자체 기준과 링크를 확인한다. 실행 결함·권한 위반과 같은 심각도로 취급하지 않는다 |

### A-02의 직접 재현과 시험 공백

- 동일한 검증 native common root에 personal-library의 안내 명령을 실행하면 exit2/unavailable, `--format native`를 명시하면 exit0/native-payload-verified였다. 실제 NAS·자료 조회는 하지 않았다.
- Wiki는 새 합성 repo·hub·config와 합성 machine-id 관측을 사용해 admission을 직접 비교했다. source는 helper 조회 지점에 도달했고 native는 그 전에 FileNotFoundError였다. helper 조회는 시험 sentinel로 대체했고 helper 실행·capture·운영 설정 변경은0회다. 이 결과는 native hook을 실제 활성화한 새 시험과 구분한다.
- 기존 capture admission 회귀는 source common을 사용하고, native 회귀는 일반 common/context 연결을 확인한다. 두 범위를 각각 통과해도 ‘활성 capture + native common’의 조합을 덮지 못했다. 새 실패는 단위 검사 통과를 조합 전체 성공으로 확대할 수 없음을 보여준다.

## 현재 구성과 관계

아래는 기존 실제 배치의 요약이며 이번 감사로 새 skill·hook을 추가한 구조가 아니다.

```text
공통 source/
├─ common/base/
│  ├─ instructions.md · workflow.md
│  ├─ skills/                 자체53개와 조건부 reference
│  ├─ references/             외부 연결·검수·전문 작업 계약
│  └─ scripts/                공통 검사·자료·도구·memory 로직
├─ adapters/{codex,claude}/   제품별 입력/출력·등록 template·연결 차이
├─ scripts/ · tests/          조립·검증·수명 관리와 회귀
└─ docs/                     요구·결정·구조·검증 추적

private source/
├─ common/base/
│  ├─ skills/                 개인9개
│  └─ scripts/                역할·common pin·백업·library·REA·capture
├─ adapters/{codex,claude}/   개인 등록과 제품별 이벤트 차이
├─ scripts/ · tests/
└─ docs/
```

읽기·실행 관계는 물리적 포함과 구분한다.

```text
제품 SessionStart → 자체 공통 지침
선택 private 시작 → source/native exact pin 검사 → 공통 context 재사용 + 개인 역할 안내
업무 요청 → 해당 자체 skill → 필요한 reference/공식 설치본 → 결과·요구 대조
도구 실행 전 → secret 검사 + upstream 검사 → 각 native 판정
도구 실행 후 → secret 결과 보호 + upstream 현재 파일 검사
선택 개인 capture → 자체 admission/결과 필드 제외 → 공식 helper (기본 비활성)
조립/전송 직전 → 실제 현재 파일·catalog·명시 scope·비밀 재검사
```

서로 다른 hook의 실행 순서를 가정하지 않는다. private는 검증한 common을 참조하며 common 내부에서 개인 패키지나 특정 호스트를 필수로 참조하는 코드는 이번 정적 대조에서 발견하지 않았다. 개인 백업·NAS·capture 활성화는 공통의 기본 경로에 포함되지 않는다.

새 생성물의 hook 선언은 common Codex5/Claude7개, private Codex5/Claude1개다. 공통 시작·사전/사후 검사와 개인 역할/capture의 목적을 구분했다. Claude private에 Codex capture 이벤트가 자동 등록된 것으로 설명하지 않는다. 실제 활성·trust·native 효과는 별도의 기존 시험 증거이며 새 패키지의 선언 수를 운영 활성 수로 세지 않는다.

## 이번에 새로 수행한 검사

| 검사 | 실제 결과·한계 |
| --- | --- |
| 파일 기준·문법 | 공통205/private70파일 hash 고정, Python81개 문법 오류0. bytecode2개는 별도 보존. 실행 전후 기존 대상 파일 변경0 확인 |
| 개별 skill 기초 검사 | 자체62개 name/description과 공식 quick_validate 통과, common/base Markdown의 상대 파일 링크 누락0. 전체 문서 의미·발동 성공이나 anchor 전체 검증이 아님. 자체 목차 차이 A-05는 별도 |
| 원래 공통 폴더 회귀 | 516개, failures1/errors20, skip0. 기존 실패 기록 유지 |
| 깨끗한 검사용 공통 사본 | 고정한205파일만 복사하고 기존 bytecode2개를 포함하지 않았음을 명시. 원래 폴더를 수정하지 않았다. 실제 pinned scanner를 사용한 전체516개 통과, skip0 |
| private 회귀 | 기존 검증 source common150파일을 명시해115개 통과, skip0. native capture 새 조합은 A-02로 별도 재현 |
| common 계약 보존 | 검사용 사본의 source150/native151파일이 양 제품 private exact pin과 각각 일치. 형식을 자동 전환하거나 기존 pin을 갱신하지 않음 |
| 공식 외부 연결 | 제품별47개 entry pin과 기존 설치 검수 기록47개씩을 현재 전체 리소스/증거 bytes로 재검증. 공식 공급자 새 설치·업데이트·업무 실행을 하지 않음. Sites 등 해당 선언에 없는 연결까지 검증했다고 하지 않음 |
| 등록 원문 보호 | 승인한 공식 BMAD 수정본 포함 catalog로 검사용 소스199파일/private68파일의 명시 scope 검사 pass·reference0. 등록된 원문 대조이며 미등록 원문·저자성·모든 변형의 부재 증명은 아님 |
| 비밀 검사 | 고정된 선택 파일 전부(205/70)를 공식 Gitleaks 기반 기존 전송 검사기로 검사해 pass. binary/인코딩 전체 비밀 부재나 게시 승인은 아님 |
| fresh 패키지 | 검사용 사본에서 guarded 공통·private × Codex·Claude4개를 실제 조립·fresh 무결성/비밀 검사. 전체 package155/58파일, 설치 payload151/54파일. 설치·trust·운영 callback은 새로 실행하지 않음 |
| 실행·배포 경계 | CI는 PR/manual·contents read·검사 전용, lifecycle은 명시 prefix와 apply/plan 대조. 이번 commit/push/설치/배포·timer/capture 활성화0회 |

## 요구 연결·개별 감사·이전 증거

- 감사 입력의 R-01~R-45를 영역·현재 근거·미결에 연결한 상세 목록은 로컬 `requirements-coverage.json`이다. 요구를 새 원문으로 바꾸거나 기존 합의를 이번 초안으로 대체하지 않았다. 모든 과거 대화에서 요구 목록 자체가 누락 없이 추출됐는지는 이 감사로 입증하지 않았다.
- kit 전체: 책임·단방향 의존·제품/설정·공식 기능·source/생성물·배포/검증 상태 관계를 대조했다. A-01~A-04 때문에 운영 적합으로 판정하지 않는다.
- skill: 전62개의 기초 형식·파일 연결·목차를 검사했고, BMAD 공통 입력/요구·조사 정책, 문서 소유권/원본 관리, 게시·도표·Android·세션/원격·개인 선택 기능의 주요 연결을 정적으로 대조했다. 전62개 모든 분기의 새 실제 모델 시험은 미실행이다.
- hook: common 검사·양 adapter·render/등록·private admission·동시 등록 목적/결과 분리를 대조하고 회귀 및 A-02 직접 probe를 실행했다. 통과가 다른 hook의 차단을 상쇄하는 allow 응답은 이 대조에서 발견하지 않았다. 기존 [native 조합](20261120-hook-bmad-native-validation.md), [private 연결](20261120-native-private-interface.md)의 관측과 이번 소스/생성물의 일치를 확인했다. 새 native canary 전수 재실행은 아니다.
- [MCP 시험](20261120-native-mcp-validation.md)은 연결·빈 DB·수명 관리 증거이고 [실제 모델 시험](20261120-real-work-compaction-validation.md)은 합성 대표 업무·수동 압축·재개 증거다. 각각 전 skill 의미 검증이나 자료가 있는 검색 품질을 증명하지 않는다. A-03은 과거 관측의 미교정 발견으로 재사용했다.

## 증거·보존과 후속

증거 정본은 `/data/projects/_scratch/tr-kit-whole-audit-20261120/`이다. baseline·revision-basis·skill inventory/형식·개별 scope와 gate·실제 회귀 로그·native 연결 실패 probe·현재 provider 검수·새 패키지·source 보존 대조를 보존했다. 기존 실패·캐시·설치본·개인 설정·자료를 삭제하거나 덮지 않았다. 상세 로그·검사용 사본·새 패키지는 운영 배포물에 포함시키지 않는다.

제안하는 다음 수정 묶음은 **A-02의 native 형식 전달2곳과 해당 조합 회귀**, **A-01의 소유 확인 후 source 준비/재검사**, **A-04/A-05의 내용 보존 교정**이다. A-03은 모델 보고 검증의 별도 보완·반복 시험으로 다룬다. 이번 감사 요청만으로 이 수정·운영 배포를 실행하지 않았다. 실제 적용 전에는 남은 미결을 다시 대조하고 대상별 설치·권한·trust·새 세션 소비를 검증해야 한다.

## A-03 후속 보완 — 별도 사용자 승인

후속3번 승인으로 공통 보고·승인 지침2파일을 보강하고 실제 양 제품 사례·최종 고정본516개 회귀를 확인했다. [별도 검증 기록](20261120-reporting-approval-validation.md)에 초기 제품 권한 불일치·출력 과장·최종 Claude 분량 위반을 보존한다. 구현/한정 시험은 완료했으나 A-03 전체 해소는 보류한다. 새 공통의 private pin 정렬·native 후보 설치와 전체 통합 검증은 후속5번이며 이번에는 운영 적용하지 않았다. 위 발견 표는 감사 당시 관측으로 유지한다.

## A-04/A-05 후속 교정 — 2026-11-23 별도 사용자 승인

[4번 교정 기록](20261123-status-docs-and-backup-order.md)에 현재 구조/요구/판정/후속 순서와 당시 이력을 구분하고 private 백업 SKILL·전환 reference의 절 순서를 정렬했다. 요구 원문·절별 내용·기존 실패/검증 이력은 보존했다. 해당 문서/목차 교정의 정적 검수이며 A-03 잔여 발견·새 후보 pin 불일치·제품 통합/운영 보류는 유지한다. 위 감사 당시 발견 표와 각 시험의 수치·실패를 덮어쓰지 않는다.

## 새 후보 영향 검증 — 2026-11-23 후속5번

[후보 통합 기록](20261123-candidate-pin-native-validation.md)에 현재 수정본의 새 source/native 묶음8개·private exact pin4개 정렬·공통516/private118개 새 회귀·양 제품 native34사례와 실제53/62개 skill 노출·공식 resource 검수·doctor/document10쌍을 남겼다. 이전 시험을 합산하지 않고 변경 영향과 제품/공통-private 관계를 대조했다. 구성·연결의 이 범위는 통과했으나 같은 작성자의 제한 감사이며 A-03 잔여 모델 문제·전 기능/실자료·전체 운영 적합 보류는 유지한다. 운영 설치/전송은6번으로 남긴다. 위 감사와 후속1~4번의 실패/미결 표시는 해당 시점의 이력이다.

## A-01 후속 정리 — 별도 사용자 승인

사용자가 캐시 대상2개의 실제 위치를 확인한 뒤 ‘아 ㅇㅇ 진행해줘’로 정리를 승인했다. 두 파일은 symlink가 아닌 현재 사용자 UID 소유의 Python3.12 bytecode였고, 내부 code filename·헤더의 source timestamp/size가 대응하는 현재 자체 소스와 일치했다. 생성 프로세스는 특정하지 못했다. 관측 가능한 fd에서 해당 파일의 열린 참조는 없었으며, 접근할 수 없는 다른 프로세스의 fd까지 확인했다고 주장하지 않는다. Git 추적 목록에는 두 파일이 없었지만 그것만으로 작업 소유권을 판정하지 않았다.

아래2개 바이트를 source 밖 로컬 기록에 보존하고 SHA256을 대조한 뒤 원래 파일과 비어 있는 부모 cache 폴더2개만 제거했다.

```text
common/base/scripts/__pycache__/upstream_guard.cpython-312.pyc
scripts/__pycache__/plugin-lifecycle.cpython-312.pyc
```

기존 원본 `.py`·검사 기준·pin·설정은 바꾸지 않았다. 기록 갱신 전 cache 외 기존 선택 파일200개의 hash가 유지됐고 재검사 뒤 source 영역의 pyc는0개였다. 이전처럼 별도 깨끗한 사본이 아니라 **원래 `/data/projects/_scratch/tr-kit-source`**에서 다음을 수행했다.

- 실제 pinned Gitleaks8.30.1을 연결한 공통 전체516개 회귀 통과·skip0.
- Codex/Claude source inventory 각150파일, 기존 private source pin과 각각 일치.
- 승인한 catalog·현재 provider 선언으로 양 제품 source 묶음 각150파일을 새 로컬 경로에 실제 조립. fresh 원문/전송·비밀 검사 통과. native 패키징·설치는 아님.

증거 정본은 `/data/projects/_scratch/tr-kit-cache-cleanup-20261120/`의 cache-inspection·cleanup·보존 bytecode·source baseline·inventory·assembly 로그와 common-regression이다. 보존 사본은 그 아래 `preserved-bytecode/`에 원래 상대경로대로 있다. 이번 결과는 A-01의 현재 조립 거부 해소이며, 캐시의 향후 재생성 방지·A-03~A-05 해결·운영 설치/배포를 뜻하지 않는다.
