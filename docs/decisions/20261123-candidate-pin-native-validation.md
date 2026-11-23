# 후속5번: 후보 패키징·exact pin 정렬·영향 검증

## 요청과 범위

2026-11-23 사용자는 앞서 제시한5번 ‘새 패키징·private pin 정렬·제품별 연결과 영향 검증’에 ‘ㄱㄱ’로 진행을 요청했다. 현재 공통/private scratch와 새 격리 prefix를 대상으로 기존 조립·검사·공식 native manager를 재사용했다. 운영 source·호스트 설정·인증·자료·timer·공식 외부 원문/설치본을 변경하거나 commit/push·운영 배포하지 않았다.

구현 변경은 private `common/base/scripts/common-contract.toml`의 source/native×양 제품 **네 digest 값 정렬**이다. 계약 schema·skill 허용 목록·제품 identity·source 기본값·검사 강도·역할은 유지했다. 공통 지침·private 기능 교정과 목차는 앞선1/3/4번의 변경을 그대로 새 묶음에 반영했다.

## 생성물·변경 영향

| 묶음·양 제품 각각 | 명세 항목 수 | 실제 포함 범위 |
| --- | --- | --- |
| 공통 source |150 | assembly.json을 별도 추가한 source 묶음 |
| 공통 native |151 | installation.json의 자기 파일 제외 명세. 실제 payload152파일·전체 package155파일 |
| private source |53 | assembly.json을 별도 추가한 source 묶음 |
| private native |54 | installation.json의 자기 파일 제외 명세. 실제 payload55파일·전체 package58파일 |

각각 Codex/Claude용으로 source4개·guarded native4개를 새 경로에 조립·fresh 검사했다. 설치본과 package·자기 파일 제외 명세의 수를 섞지 않는다. 모든 파일 bytes·이름·metadata·pin은 실제 목록으로 대조했다.

- 공통 source의 이전 검증본 대비 변경은 instructions/workflow 원본2개와 생성 제품 지침·workflow2개다. native는 제품 지침 루트 파일을 시작 hook으로 대신하므로 공통 원칙·두 workflow 경로와 제품 manifest의 시험 버전이 달라진다.
- private source의 변경은 exact pin, Wiki 형식 전달 코드, personal-library 연결 명령, artifact-backup 본문·전환 reference의5파일이다. native는 여기에 제품 manifest의 시험 버전이 추가된다. 파일 삭제·외부 본문 동봉은 없다.
- 공통 native 버전은 `0.0.0-integration.20261123`, private는 `0.0.0-private-integration.20261123`다. 운영 release/commit 번호를 만든 것이 아니다. **native exact pin은 이 manifest 버전도 포함한다.** 운영 버전을 바꾸면 새 manifest·공통 native pin·관련 private 묶음을 함께 재검증해야 한다.

```text
공통 source → 기존 assembler/package → 양 제품 source/native 후보
                                     ↓ exact inventory4개 대조
private source → common-contract digest4개 정렬
              → 검증된 공통 조립·수명 관리 재사용 → 양 제품 private 후보

새 격리 제품 설정 → 공식 manager 설치 → native UI/초기 주입·callback
                → private 제거/공통 보존 → 공통 단독 확인 → 시험 등록 제거
```

실행/검사 책임·기존 skill/hook·adapter 배치와 private→common 의존은 유지했다. 새 위임기·차단기·업무 skill을 추가하지 않았다. 선택된 공식 provider/resource와 runtime은 source 밖 기존 위치에 있고 패키지에 포함되지 않는다.

## 실제 검증 결과

| 검사 | 관측과 범위 |
| --- | --- |
| 전체 회귀 | 실제 pinned Gitleaks8.30.1을 연결한 원래 공통516개·새 source 공통과 연결한 private118개 통과, skip0. 이전 숫자의 재인용이 아닌 이번 실행 |
| exact 계약 | 새 source/native4개 직접 admission 통과, 이전 source/native4개 거부. 네 digest 외 TOML 의미와 역할 정책 bytes 보존. 추측·자동 fallback·검사 완화 없음 |
| 공식 연결 | 제품별47개 entry와 명시한 공식 설치 검수 기록·전체 resource/evidence bytes를 재대조. 새 공식 설치·업데이트·외부 업무 실행은 하지 않음 |
| native 설치/발견 | Codex0.167.2·Claude Code2.1.329의 공식 manager로 새 격리 설정에 공통/private 설치. 설치 cache 전체 bytes/목록과 manifest 대조. native API 입력에서 실제 노출 이름을 source와 대조해 각 제품 공통 단독53개·공통+private62개 일치 |
| 초기 주입 | 별도 후보 정책 append 없이 native 시작 hook을 사용. 합성 API가 받은 요청에서 새 공통 원칙과 private 역할 전달을 확인. 공통 단독에는 개인 역할 문맥 없음 |
| native callback34사례 | 공통 단독12·공통+private/실패 경계22사례. 정상 Python 집합/마커, 전체 환경 출력·일괄 staging·합성 비밀 입력·등록 외부 원문 복제 차단, binding/scanner 부재 차단, 합성 비밀 결과 비전달, source 연결과 공통 부재를 대조. 합성 API 응답과 실제 native hook이며 실제 모델의 판단 품질 시험은 아님 |
| 제품별 시작 실패 | 공통 부재 시 Codex는 SessionStart continue=false로 API 요청 전에 종료. Claude는 준비 실패·보류 지침을 API에 전달하고 세션 전체를 강제 차단하지 않았음. 같은 실패 계약을 같은 제품 효과로 확대하지 않음 |
| 형식 전달 조합 | 양 제품×source/native/default-source/오형식/부재10사례에서 설치된 private의 Wiki doctor와 document 명령을 실제 실행. 정상6개는 공식 helper의 entry/resource/pin까지 확인해 ready, 거부4개는 각 CLI 계약대로 실패. helper 실행/capture는0회, 합성 hub 변경0 |
| skill 형식 | 자체62개 모두 공식 system skill-creator quick_validate 통과. 기초 형식이며 전 분기/모델 의미 보장 아님 |
| 제거·보존 | private 제거 뒤 양 제품에서 공통 등록·bytes 보존. 이후 공통 단독 시험과 공통 제거·설치 목록0 확인. Claude 보존 cache는 별도 기록하며 강제 삭제하지 않음 |

Codex의 시험 hook10개는 native `/hooks` UI에서 각각 검토·신뢰했다. ‘Trust all’·신뢰 DB 복사/편집은 하지 않았다. 첫 UI 입력은 시작 대화상자 준비 전에 도착해 신뢰 없이 계속됐고, 이 실행을 검증 성공으로 세지 않았다. UI를 다시 열어 개별 신뢰를 완료한 뒤 실제 시험했다. 운영 계정의 hook trust를 갱신한 것이 아니다.

## 시험기 오류와 보존

- 첫 provider 검수는 BMAD에 수정본 전의 review 경로를 선택해 identity guard가 거부했다. 선언/원문을 바꾸지 않고 승인된 공식 수정본의 기존 검수 기록을 명시 선택해94개를 대조했다. 초기 입력 불일치를 source 구현 실패나 검수 통과로 세지 않는다.
- 첫 doctor 검증기는 거부 결과도 stdout JSON/exit2일 것으로 가정했다. 실제 doctor 계약은 일반 stderr/exit1이고 document CLI는 JSON/exit2다. 두 계약을 구분해10사례를 다시 확인했다. kit의 실패 응답을 통과시키려고 변경하지 않았다.
- 원시 native 결과에는 의도한 합성 토큰이 있어 현재 세션의 비밀 검사에서 출력이 가려진1회가 있었다. 같은 원문을 다시 출력하지 않고 저장된 결과의 실행/차단·비전달 여부만 확인했다. raw 증거는 로컬 전용으로 남긴다.

## 감사·한계·다음 범위

기존 plugin-authoring의 kit 작성/전체 감사, 관련 skill/hook 감사와 실제 구조·읽기·행동 시험 기준을 적용했다. 변경 범위·공통/private 단방향 의존·제품의 실제 입력/결과·형식·구조/생성물·권한·원문/비밀 검사와 기록을 대조했다. 동일 작성자의 범위 제한 감사이며 독립 전문 감사·모든 과거 요구 원문/정정의 전수 대조는 아니다. 이전 전체 감사는 바뀌지 않은 영역의 참고로만 재사용했다.

이번 단계의 구성·연결 검증은 통과했다. A-01/A-02/A-04/A-05의 해당 수정과 새 묶음 반영을 확인했지만 **전체 업무/운영 적합은 계속 보류한다.** A-03 실제 모델 분량 위반, 자동 update404 미지원, 자연 발동·자동/장기 압축·모든 skill·실자료/NAS/기존 DB·실제 백업/timer·capture·운영 복구는 이번 검사로 해소하지 않는다. 앞선3번의 실제 모델 지침 시험과 이번 native 전달 증거를 구분하며 새 실제 모델 비교를 실행한 것으로 보고하지 않는다.

특히 이번 native 시험은 도구 실행 전후·시작/종료·비활성 capture 조합의 관측이다. 실제 PreCompact 이벤트/압축, 활성 capture/helper 쓰기, 모든 입력/동시 실행·native timeout을 새로 전수 실행한 것은 아니다. 변경 없는 검사 코드의 직접 경계/실패 시험은 이번 전체 회귀에 포함하되 실제 native 관측과 구분한다. 기록된 BMAD update404는 이번에 네트워크 재조회하지 않고 기존 보류로 유지했다.

후속6번은 승인된 운영 대상·전송 범위·실제 runtime/provider·현재 세션/trust를 확인한 뒤 commit·설치/배포·새 세션을 검증하는 단계다. 이번 격리 성공만으로 기존 세션을 재시작하거나 운영 timer/수집을 활성화하지 않는다.

로컬 정본은 `/data/projects/_scratch/tr-kit-integration-20261123/`의 변경 전 hash·공통/private 묶음·pin 비교·회귀 로그·공식 resource 검수·native 입력/결과·doctor·등록 제거·감사/보존 기록이다. 원시 API 로그·합성 토큰·기기 hash·설정·scanner 복제와 상세 증거는 로컬 전용이며 배포물/저장소에 포함하지 않는다.

마지막 대조에서 현재 source의 유효 조립 입력과8개 산출물 bytes가 일치했고, 자체 docs/base/adapter의 로컬 파일·anchor336개에 누락이 없었다. 관측 가능한 process cwd에는 이 시험 경로의 잔존 process가 없었으나 접근하지 못한236개 process의 상태까지 확인했다고 주장하지 않는다. 양 제품 설치 목록은 시험 plugin0개였고 Claude manager가 보존한 cache·로컬 증거는 삭제하지 않았다.
