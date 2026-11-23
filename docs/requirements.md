# 요구 목록

대화에서 추출한 누적 요구의 근거·반영 위치를 연결한다. 초기 목록은2026-11-13 대화에서 시작했으며 이후 행에 해당 후속 요청을 기록했다. **모든 과거 원문/정정의 누락 없는 대조를 완료했다는 뜻은 아니다.** 명시 요구·채택 결정과 작성 요청/제안을 구분하고 파일 존재만으로 새 합의를 확정하지 않는다.

아래 반영 열은2026-11-23 현재 연결이다. 당시 수치·실패·미실행의 상세는 각 결정과 [검증 이력](verification.md#검증-이력--각-시점의-원래-범위)에 보존하며 현재 후보와 같은 revision으로 취급하지 않는다. [현재 판정](verification.md#현재-판정--2026-11-23)의 후속5번 pin 정렬 결과·잔여 행동 문제와 운영 보류를 함께 적용한다.

| 번호 | 요구 | 합의 상태·근거 | 현재 반영·검증 연결 |
| --- | --- | --- | --- |
| R-01 | 외부 공식 설치본을 연결하고 외부 원문 복제·동봉·원문 및 사본 변형을 금지 | 확정 | plugin-authoring·instructions/workflow와 원문 보호/조립 gate 구현. 실제 native 정상·차단은 R-41, 전체 관계 감사는 R-46. 등록 원문·지원 도구/입력의 관측 범위이며 모든 복제/변형 방지 보장은 아님. |
| R-02 | 승인 범위 안에서는 계속 진행하고 추가 범위는 정리·보고 후 승인 | 확정 | 공통 instructions/workflow·plugin-authoring에 반영. R-42/R-45의 이전 native/대표 압축과 R-48의 실제 모델 지침 시험을 구분. R-50에서 새 후보 native 전달·연결 검증. 자연 발동/새 모델 압축·운영은 별도. |
| R-03 | 조회의 정상 부수효과와 별도 관리 변경을 구분 | 확정 | common/base/workflow.md의 승인과 조회 표에 정상 로그·API 캐시·별도 저장·직접 재색인·파일 변경·잠금·대규모 조회·미확인 효과를 연결. 실제 시험은 verification.md 참조 |
| R-04 | 명시적 요구·금지, 확정 결정, 제안, 미결을 구분해 적용 범위별 관리 | 확정 | plugin-authoring 입력과 공통 instructions/workflow의 요구·결정 연결에 반영. 대표 새 세션 시험과 압축·실제 기록 소비 검증은 구분 |
| R-05 | 기준 본문은 한 곳에서 관리하고 요구 목록은 근거·상태·반영 위치를 연결 | 확정 | 이 문서는 상태·위치를 연결. 상세 기준은 plugin-authoring 본문과 각 reference에서 소유 |
| R-06 | 공통 책임과 Codex·Claude 제품 차이를 분리 | 확정 | architecture.md의 공통/제품 책임과 조립·lifecycle. 이전 R-41/R-42와 새 R-50의 양 제품 격리 연결을 구분. 전체 업무/운영 효과는 별도. |
| R-07 | 검사 적용 범위와 실행 수단을 구분 | 확정 | plugin-authoring·hook 기준과 실제 공통 검사/양 adapter에 반영. 이전 native 등록·callback/조합의 한정 검증은 R-41/R-42. 모든 적용 대상·입력/운영 효과를 검증한 것은 아님. |
| R-08 | hook 작성·수정·검수에 합의한 다섯 항목 적용 | 확정 | references/hook/authoring.md와 audit.md 작성. 합성/실제 native 검증은 구분 |
| R-09 | kit·skill·hook 저작과 대상별 감사를 한 진입점에서 구분 | 명칭·구조 확정 | plugin-authoring 본문에서 6개 대상별 분기 연결. 검증 범위는 verification.md 참조 |
| R-10 | 항상 필요한 고유 공통 판단·분기는 SKILL.md, 조건부 공통 절차는 shared, 대상별 저작·감사는 skill/hook/kit 아래 여섯 reference로 구분 | 구조 변경 요청 반영 | architecture.md; 본문·shared 3개·대상별 6개 기준 작성 |
| R-11 | 검증 상태는 docs에 기록하고 상세 로그·원본 증거는 로컬 작업 기록과 구분 | 확정 | verification.md |
| R-12 | Codex·Claude 동일 검사 항목과 제품별 절차, 새 세션·압축 이후 행동을 구분해 검증 | 사용자 요구 | 양 제품 native R-41/R-42, 실제 대표 모델/수동 압축 R-45, 보완 지침 명시 시험 R-48. R-50 새 후보 native 전달/경계 시험과 새로운 실제 모델·장기 압축/자연 발동을 구분. |
| R-13 | 작성·수정 전후 skill·hook·script의 배치·역할·연결·발동·적용 범위와 변화를 터미널 도표로 제시 | 사용자 명시 요구 | 본문과 shared/structure-view.md에 반영. 도표 9회 검증 및 hook·kit 행동 시험은 verification.md 참조 |
| R-14 | 외부 저작 기능 실제 적용, 읽기·호출 흐름 검사와 작성 후 대상별 감사 연결을 본문에 반영 | 사용자 작성·검수 요청 이력 | common/base/skills/plugin-authoring/SKILL.md와 각 작성/감사·shared 연결 구현. 공식 skill-creator 적용·형식 validator·읽기/행동 범위는 verification.md의 이력과 현재 판정에서 구분. 파일 존재로 문안 전체의 개별 승인을 주장하지 않음. |
| R-15 | 항목화 시 중요 내용·조건·예외·금지를 삭제하거나 표현을 넓혀 해석 여지를 늘리지 않음 | 사용자 명시 요구 | SKILL·shared 저작 기준과 순차 정적/대표 행동 시험에서 대조. 해당 이력과 R-45의 대표 보존 관측을 재사용 범위 내에서 구분하며 전 요청의 보존 보장은 아님. |
| R-16 | 기존 skill-authoring을 참고해 목차·분기·연결·지원 자료·수정 보존·형식 검증을 보강하고 작성된 전체 5개 지침을 3회 검수 | 사용자 작성·검수 요청 | skill/authoring.md 보강, 본문·shared 자체 규격 정렬, 정적 검수 3회. 이후 확장 10개 기준의 시험 상태는 verification.md 참조 |
| R-17 | skill 감사에서 작성 기준을 복제하지 않고 항목별 증거·검사 방법·판정·보고를 정의 | 사용자 작성 요청 | references/skill/audit.md 작성. 기존 6개 지침의 독립 정적 감사 수행. 새 모델에 해당 감사 분기를 적용하는 행동 시험과 구분 |
| R-18 | 파일 구조와 읽기·실행 흐름을 분리해 보여주고 포함·참조·실행·보고 관계를 섞지 않음 | 사용자 명시 요구 | shared/structure-view.md·reading-flow.md·skill/audit.md에 반영. 도표3사례×3회는 당시 Codex 명시 적용 결과이며 다른 제품·전 기능 도표 검증으로 확대하지 않음. |
| R-19 | 도표 표현을 반복 행동 시험한 뒤 후속 진행 판단 | 사용자 시험 요청 | Codex 도표3사례×3회·판정9/9의 당시 증거 보존. 후속 양 제품 native/모델·압축 결과는 R-41~R-45의 별도 대상이며 도표 전 범위 Claude 검증을 뜻하지 않음. |
| R-20 | 현재 skill 감사 후 hook·kit 저작/감사를 작성하고 정적 검수·반복 행동 시험·보완으로 진행 | 사용자 절차 승인 | 독립 정적 감사와 reference 4개 작성, 3관점 검수·실패 보완·반복 회귀 시험 수행. 최종 15회/75항목 통과, 범위·미실행은 verification.md 참조 |
| R-21 | 기록한 합의를 반영해 scratch의 실제 보호 hook을 설계·작성·반복 검사·감사. 운영 설치와 skill 이관은 분리 | 2026-11-17 사용자 진행 요청 | decisions/20261117-upstream-guard.md의 초기 작성/실패 보존. 이후 사전·사후·fresh gate는 R-22, native 조합은 R-41/R-42. 운영 적용은 별도. |
| R-22 | 사전·실제 결과 검사 조합을 채택하고 격리·OS 쓰기 통제는 이번 구성에서 제외. 유사성은 주된 차단 기준에서 제외하고 적용 대상부터 판별 | 2026-11-17 후속 대화에서 채택 | 사전·실제 결과·fresh 검사/조립 구현. 이전 native 등록·한정 차단은 R-41/R-42, lifecycle 전송 후보 검사 구현은 R-37. 실제 외부 전송·미관측 입력의 전면 차단을 보장하지 않음. |
| R-23 | 기존 두 세션의 시크릿 차단·오탐을 조사하고 개편 시 반영. 개편 전 플러그인 수정·배포는 제외 | 2026-11-17 사용자 요청 | decisions/20261117-secret-guard-findings.md. go.sum·명령 경계 오탐 재현, Sites 정오탐 미확인. 원문 보호 검사로 해결 처리하지 않음 |
| R-24 | 원문 보호 hook 다음에 시크릿·커밋 검사도 새 구조에서 수정·구현·검수한 뒤 나머지 이관 진행 | 2026-11-17 사용자 실행 요청 | decisions/20261117-secret-hook-implementation.md의204개×3회는 당시 결과. 이후 G1 등록/chain·R-41 native·전체 감사/후속 회귀와 구분. 기존 운영 hook 교체·배포는 아직 하지 않음. |
| R-25 | 기존 공통 기능의 1 공통원칙/요구연결, 2 공식연결·보안/최소조립, 3 공간·세션 기능을 순서대로 묶어 scratch 이관·검증 | 2026-11-17 사용자 진행 승인 | decisions/20261117-migration-1-3.md. 자체 source·공통 지침·7개 skill 이관, 조립기 작성. 검증과 미이관 기능은 verification.md 참조. 운영 설치·배포 제외 |
| R-26 | 보류한 통합 검증과 미이관 기능을 구분하고4번 BMAD·조사·설계/개발 연결 이관 진행 | 2026-11-17 사용자 승인 | 자체 연결31개·source 경로 보존 이관 이력은 해당 결정에 보존. 이후 공식 연결 R-40/R-41·Git G1/R-32·native/압축 R-42/R-45와 구분. 전 skill 실제 업무 검증은 아님. |
| R-27 | 5번 문서 작성·시각화·계정 전용 게시 기능 이관 | 2026-11-17 사용자 승인 | decisions/20261117-migration-5.md. 자체 wrapper5개·제품 adapter2개·기존 scanner 재사용 payload 진입점과 분기 작성. source/직접/조립과 실제 공식/native 게시 검증을 구분 |
| R-28 | 6번 자료 보관·검색·작업 기록·경험·지식 연결을 scratch로 이관·검수 | 2026-11-17 다음 작업 진행 승인 | decisions/20261117-migration-6.md의 source 이관. 이후 실제 격리 memory MCP는 R-44, private 형식 전달은 P-19에 연결. 실자료/NAS/자동 수집·일반 문서 sync 실행은 별도. |
| R-29 | 7번 Android·Wear OS 기능을 scratch에서 이관·검수 | 2026-11-18 진행 승인 | decisions/20261118-migration-7.md. 공식 기능 자체 연결6개·공통 범위/검증 기준·기존 BMAD build 조건부 연결. 실제 앱/SDK/기기 변경·테스트·운영 설치 제외 |
| R-30 | 공통7번 이후 private source 기능 이관·검수 | 2026-11-18 진행 승인 | 별도 tr-kit-private scratch source의 docs/requirements.md·architecture.md·verification.md가 개인 구현 정본. 공통 구현을 복사하지 않고 검증된 common source inventory pin에 연결. 실제 운영 전환/배포 제외 |
| R-31 | 전체 기존/신규 기능·도구의 가져옴/대체/미이관/제외·별도 계획과 후속 순서 대조 | 2026-11-18 목록 정리 진행 승인 | docs/migration-status.md. 기존 source194파일·dependency/제품 ID·지원 도구·CI를 대조. 구현/역할/설치/배포 변경 없이 현황·권장안을 기록 |
| R-32 | G1의 Git guard 등록·chain·status/rollback 및 산출물 예외 강제 구현·검수 | 2026-11-18 사용자 “G1 가자” | scratch 자체 source와 임시 Git 저장소 시험. 기존 운영 저장소 hook 등록·설치·배포는 제외. decisions/20261118-g1-git-enrollment.md |
| R-33 | PTBMAF·Design Doc 도입/구현, Obsidian 다기기 열람, NotebookLM CLI 논문 분석 활용 구상을 보존 | 2026-11-18 사용자 기록 요청 | migration-status.md의 후속 도입 구상. 구현·설치·GitHub 전송·실논문 업로드는 이번 승인에 포함하지 않음 |
| R-34 | G2 공식 도구 준비·receipt/버전·실행 검증 절차 구현·검수 | 2026-11-18 사용자 “G2 ㄱㄱ” | scratch toolchain/setup/verify source와 격리 protocol 시험. 실제 도구 신규 취득·설치·provider/hook·운영 전환은 제외. decisions/20261118-g2-toolchain.md |
| R-35 | G3 기존 선언 읽기량 측정기를 새 구조로 이관·검수 | 2026-11-18 사용자 “다음 ㄱㄱ” | context_check 공통 로직/CLI·source cases·reading-flow 연결. 문자/metadata·중복/부분 겹침·미측정과 측정/비증가 비교를 분리. 실제 token·자연 발동·운영 설치는 제외. decisions/20261118-g3-context-check.md |
| R-36 | G4 Claude-Mem MCP·worker 수명 관리·health 연결 source 작성·격리 검수 | 2026-11-18 사용자 “다음 G4 ㄱㄱ” | decisions/20261118-g4-claude-mem.md. 공식15.2.1 entry 직접 연결·명시 binding·양 제품 설정 fragment. 공식 설치/개인 자료/기존 worker/native 등록/운영 배포는 제외하고 검증 층위를 분리 |
| R-37 | G5 공통 양 제품 native 패키지·격리 설치/업데이트/제거/복귀·검사 전용 CI 작성·검수 | 2026-11-18 사용자 “G5 ㄱㄱ” | G5 구현·초기 Codex 시험 이후 R-41/R-42의 양 제품/private, R-44 MCP, R-50 새 후보 격리 설치·제거/정확한 pin을 연결. 운영 대상 설치는6번. |
| R-38 | G6 개인 백업 구3파일→신9파일 전환·보존/실패/복귀 source 검수 | 2026-11-18 사용자 “G6 ㄱㄱ” | 별도 private scratch의 P-13·docs/decisions/20261118-g6-backup-transition.md가 구현/검증 정본. 공통 코드·private common pin·운영 timer/자료/원격은 유지. 현재 상태는 migration-status.md |
| R-39 | G7 공식 provider 설치 근거·필수 resource·제품/업데이트 검수와 공통/private 연결 보완 | G6 뒤 사용자 후속 “ㄱㄱ” | decisions/20261118-g7-provider-review.md. 기존 resolver/공식 manager 재사용, 무변형 외부 설치본 검수·새 source common pin 대조. 운영 설치·신뢰/자료/실제 worker·원격 전송 제외. source 구현과 전체 공식/native 실행 검증을 구분 |
| R-40 | 후속1번: 공식 provider·runtime을 격리 준비하고 실제 호출·실패/미지원 검증 | 2026-11-20 사용자 “1번부터 ㄱㄱ”, 후속 “아 공식 원문으로 해줘 ㅇㅇㅇ 공식기준이야” | 공식 원문 채택·격리 실행과 초기 실패는 decisions/20261120-official-provider-validation.md. 이후 BMAD 오류/새 source 오탐 보완은 R-41. 자동 update404는 미지원이며 운영 구 hook과 구분. |
| R-41 | 후속 hook 오탐 보완·승인한 공식 BMAD 수정본 채택과 양 제품 native 격리 검증 | 사용자 다음 작업 진행 및 “공식 수정본으로 채택·검증” | decisions/20261120-hook-bmad-native-validation.md. 자체 오탐 보완·공식867c546e·native30사례 당시 결과. 후속 private R-42·MCP R-44·모델/압축 R-45, 현재 후보 전체 통합/운영은 별도. |
| R-42 | private native 패키징·공통 설치본 연결 수정과 격리 검증 | 사용자 “일단 넘어가고 다음꺼 ㄱㄱ”. 앞서 제시한 private native 후속 범위 | decisions/20261120-native-private-interface.md의 실제 설치/발견·시작·제거와 callback. 새 지침/형식 교정/목차 후보는 R-50에서 새로 조립·pin/격리 연결 검증. 실자료/운영·전 기능 모델 품질은 별도. |
| R-43 | 실제 Claude 새 세션에서 정상·연결 실패 응답 비교 | 사용자 “확인해야 할 것 같다까지 되면 상관없다”, 후속 “권장하는 거 먼저 해줘봐” | 추가 실제 Claude 정상/실패 응답 시험은 native-private-interface 기록. 도구 미노출이므로 실제 실행 보류/우회 방지 보장 아님. 보고 문제는 R-48에서 보완했으나 분량 위반 잔여. |
| R-44 | 다음 Claude-Mem MCP 실제 등록·연결 격리 검증 | 사용자 “ㅇㅇ ㄱㄱ”, 직전 명시한 다음 작업은 MCP 실제 등록·연결 | decisions/20261120-native-mcp-validation.md. 양 제품 native19개 도구·빈 DB 조회/실패·자동 미기동/명시 stop·제거·잔존 확인. Python/Chroma 시험 준비와 운영/실자료/모델 선택·전체 감사·배포를 구분 |
| R-45 | 새 kit 실제 모델 업무·압축/재개를 격리 환경에서 검증 | 사용자가 샌드박스 시험임을 확인한 뒤 “아아 그래 진행해줘” | decisions/20261120-real-work-compaction-validation.md. 양 제품 합성 대표 업무·native 수동 압축·동일 대화 프로세스 재개·요구/원본/형식 보존 대조. 초기 시험 실패와 Claude 잔여 보고 오류를 분리. kit 구현·운영 배포·실자료·자동/반복 장기 압축은 제외 |
| R-46 | 직전 발견을 포함한 공통/private 전체 kit 감사 | 직전 제시한 다음 작업에 사용자 “ㄱㄱ” | decisions/20261120-whole-kit-audit.md. 전체 관계·62개 기초 형식/연결·현재 provider·hook·회귀·fresh 조립 대조. native 형식 누락/캐시/보고·상태 충돌 등 미해결과 전체 적합 보류를 명시. 구현 자동 수정·운영 설치/배포는 제외 |
| R-47 | A-01의 명시 cache2개 정리와 원래 소스 재검증 | 사용자에게 두 경로를 설명한 뒤 ‘아 ㅇㅇ 진행해줘’ | decisions/20261120-whole-kit-audit.md의 A-01 후속 정리. 바이트 보존 후2개 제거·원래 폴더516개 회귀와 양 제품 source 조립·기존 pin 대조. 생성 주체 미확인·미래 재생성 방지 미구현과 초기 실패를 구분. 검사 완화·운영 설치/배포 없음 |
| R-48 | A-03의 미확인 설명·불필요한 재승인 보완과 양 제품 실제 시험 | 앞서 제시한 후속3번에 사용자 “3번 ㄱㄱ” | decisions/20261120-reporting-approval-validation.md. 공통2파일·516개 회귀와 단계별 모델 시험, 잔여 분량 위반·출력 귀속 기록 유지. 새 native 후보 전달·pin 정렬은 R-50이며 새 실제 모델 비교를 뜻하지 않음. |
| R-49 | A-04 현재/과거 문서 정리·A-05 개인 백업 목차 정렬과 검수 | 직전4번 제시에 사용자 “ㄱㄱ” | decisions/20261123-status-docs-and-backup-order.md. 현재 요약/근거와 이력 분리, 요구 원문/금지·이전 실패 유지. 백업 SKILL/전환 reference는 내용 보존 후 절 위치만 변경. 새 제품 통합·pin·운영 적용은 제외 |
| R-50 | 새 후보 묶음·private exact pin 정렬·양 제품 연결과 영향 회귀/감사 | 직전5번 제시에 사용자 “ㄱㄱ” | decisions/20261123-candidate-pin-native-validation.md. 네 digest만 정렬·새 묶음8개·516/118회귀·native34사례·실제53/62 skill 노출·doctor/document10쌍. 운영·실자료·새 실제 모델 비교는 제외 |
| R-51 | 실제 운영 대상에 공식 provider·원문 보호 runtime 설정을 연결·검증한 뒤 커밋·배포 계속 | 사용자 ‘운영 연결 보완·검증 후 배포 계속’ | decisions/20261123-host-runtime-connection.md. 공통525개/private129개 회귀·세 호스트 공식47개 연결·native 설치·Codex 개별 trust·새 지침 전달 확인. 실제 명령은 dev01/Claude 성공, nas-vm sandbox 오류 미실행. 전체 업무 적합·자료/worker/timer 활성화와 구분 |
| R-52 | 재부팅 대비 exact UUID 재개 목록의 준비·조회와 나중 선택 restart/restore/verify, 예외와 요청 세션의 수동 재시작 목록 | 승인 계획 `plan-session-restart-batches.md` 및 수동 항목 표시 추가 | [구현·한계](decisions/20261123-session-restart.md). session_restart.py의 호스트 로컬 배치·진행 기록, session 분기와 orca-update 연결. 준비는 종료 없음, 예외는 입력 없음, 첫 실패 뒤 중단, identity/권한 대조와 소비 증거 분리. 소유 Codex prepare/restart/restore와 Claude prepare/helper cold restore 통과. 최종 공통600/private129개·8묶음/pin 대조는 검증 기록 참조. 호스트 rollout·실제 reboot는 미실행, Claude 즉시 restart는 수동. [조회 제한·진단 거부·현재 응답 신원과 증거 결합·복원 직전 대조](decisions/20261123-session-query-hardening.md)는 source와 소유 로컬 회귀로 검증. [지연 status·수신자 home·접수된 조회만 있는 중단 준비 검증](decisions/20261123-session-preparation-compat.md)은 같은 배치와 실패 증거를 보존하며 원 queried 대상에만 적용. [동일 cursor의 Codex 새 화면 응답 증명](decisions/20261123-codex-status-screen-proof.md)은 원 이력 overlap과 새 marker/card를 독립 확인하며 stream 충돌·동일 반복은 거부. 실제 NAS 복구·배포는 별도 검증 |
| R-53 | 세션 보존을 포함한 승인 native CLI 업데이트를 기존 공식 관리자에 연결하고 설치 방식·계정·채널·권한 및 예외를 보존 | 사용자 dev01 Codex 업데이트 승인 및 이후 nas-vm Codex/inno-desktop Claude 업데이트 흐름 연결 요청. 계획의 비frozen change log에 기록 | [추가 연결·실패 기록](decisions/20261123-session-restart.md). prepare UUID/예외 → 승인 관리자 → 실제 버전/재개 canary. Orca 업데이트와 독립 판정, 무승인 자동 업데이트 금지. 실제 실패를 보존하며 권한 보존 미확인은 호출 전 수동 보류. 최종 패키지/pin 검수는 검증 기록 참조. 원격 native 업데이트·운영 적용은 미실행 |
| R-54 | 관측된 기존 권한 옵션을 확인해 그대로 보존하되 일반 권한 증가·전역 설정 변경·임의 flags 재생은 금지 | 사용자 “기존 권한 옵션을 확인해 그대로 보존” 명시 선택과 default/Custom 추정 금지 정정. 비frozen change log에 기록 | [권한 보존 후속](decisions/20261123-session-restart.md). runtime_refresh의 native mode/단일 resume 구성기를 refresh/restart/restore에서 재사용. 기존 Codex Full Access와 Claude2.1.330 exact bypass만 고정 옵션 허용. 미확인 모드는 exit/create 전 수동, 부재 legacy 추정 금지·uncertain 보존. 이전 실패·기본 Custom canary는 별도 과거 결과 |

번호는 이 작업 공간의 추적용이다. 요구 추가·정정 시 기존 번호를 다른 의미로 재사용하지 않는다. 미작성·미구현·미검증을 완료로 처리하지 않는다. 상세 기준 본문은 담당 지침 한 곳에서 관리한다.
