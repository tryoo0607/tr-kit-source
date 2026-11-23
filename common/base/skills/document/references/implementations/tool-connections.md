# 도구 연결

선택한 자료·기록 요청에 실제 외부 기능을 사용할 때 해당 절과 공통 입력/실패 기준만 읽는다. 제품별 설치본·MCP·CLI를 연결하며 외부 본문과 runtime을 kit에 동봉하지 않는다.

## 입력과 전제

- 요청 동작·대상 소속·기존 정본 포인터·저장/검색 범위·권한을 전달한다. 조회와 쓰기, 로컬 보관과 전송은 별도다.
- 공식 skill 연결은 [공통 외부 연결](../../../../references/external-connection.md)을 따른다. CLI는 실제 설치 경로·버전·해당 설치본 도움말을 먼저 확인한다. 이 문서의 버전은 기존 연결 기준이며 현재 호스트 설치·실행 성공 증거가 아니다.
- 필요한 서버/도구만 선택한다. 실제 세션이 노출하는 식별자와 schema를 확인하고 유사 이름의 다른 서버로 대체하지 않는다. 부재·오류·0건 결과를 구분한다.

## 수행 방법과 절차

### 중앙 원본 — 자체 실행기와 공식 CLI

- 자체 [assets.py](../../../../scripts/assets.py)는 경로·출처/최신성·실패 보존과 명시 범위 검색만 소유한다. Docling 변환·QMD 검색 엔진은 외부 공식 설치본을 호출한다. 기존 연결 기준은 Docling 2.145.0·QMD 2.8.3이며 현재 CLI 계약이 다르면 영향받는 실행을 보류한다. 설치·모델 다운로드·원격 fallback은 수행하지 않는다.
- `scope`는 확인한 group/project 식별자와 설정으로 경로만 계산한다. `prepare`는 계획, `prepare --apply`만 originals/extracted를 함께 만든다. `--scope`는 명시 경로를 직접 선택하며 `--config`는 파일 하나를 선택한다. 명시 config 부재·미지원 필드는 오류다. 기본 config가 없으면 기존 규격의 기본 루트만 계산한다. 설정 검증은 [profile 규격](../../../profile-setup/references/config-schema.md)이 소유한다.
- `extract --scope <scope> --relative <원본 상대경로>`는 해당 추출 결과와 provenance를 쓴다. 실제 사용 도구·허용 옵션·출력과 모델 준비를 확인하고 승인 범위에 포함한다. 오프라인 환경 변수는 모델 다운로드 방지 의도이며 OS 네트워크 격리 보장은 아니다. 명시 실행 파일/옵션은 신뢰된 선택에 한정하며 임의 명령의 안전성을 helper가 인증하지 않는다.
- `index --scope <scope>`는 파생 corpus·QMD config/cache·색인 상태를 쓴다. 별도 변경 동작이다. 상태 루트는 TR_ASSETS_STATE_ROOT, 없으면 XDG_STATE_HOME 또는 ~/.local/state 아래 tr-kit/assets다. 원본 범위 내부 상태·symlink 경유 쓰기는 거부한다. 기본 조회에서 자동 실행하지 않는다.
- `search --scope <좁은 범위> [--scope <다음 허용 범위>] --query <검색어>`는 명시된 순서만 조회한다. QMD가 없거나 실패하면 파일명/경로 결과와 미색인 상태를 표시한다. 내용 검색·0건 성공으로 보고하지 않는다. QMD 자체 검색의 통상 cache 효과와 관리 명령을 구분하며 실제 설치본이 별도 생성/갱신을 요구하면 승인 범위를 확인한다.
- fresh 추출만 corpus 후보가 되고 hit를 현재 원본·추출 hash와 다시 대조한다. 원본 누락은 삭제 승인으로 취급하지 않으며 이전 corpus 자동 삭제는 없다. 전역 대규모 검색의 시간/부하는 실행 범위에 포함한다. helper는 단일 작업자용이며 동시 추출/색인·적대적 filesystem 경쟁의 원자성을 보장하지 않는다.
- Git 전역 제외·tr-local-docs 추적 예외는 [profile 연결 절차](../../../profile-setup/references/git-excludes.md)가 소유한다. 원본 준비를 Git 설정 변경으로 확대하지 않는다.

### BMAD — 작업 정본

- 현재 작업 상태·계획·요구·검증은 기존 BMAD 또는 이미 채택한 작업 정본에서 확인한다. 필요한 [BMAD 연결](../../../bmad/SKILL.md)에 진입하고 정확한 ticket/initiative/산출물을 전달한다.
- 상태 조회를 build·재계획·새 initiative 생성으로 확대하지 않는다. 경험·Wiki와 다른 결과가 나오면 현재 정본·적용 시점·미결을 비교하며 동일 내용을 세 도구에 복제하지 않는다.

### Claude-Mem — 경험 후보와 상세

- 경험 검색은 [mem-search](../../../mem-search/SKILL.md)를 통해 공식 설치본을 선택한다. 후보 search → 필요한 timeline → 선택 ID의 상세 순서와 실제 schema는 공식 skill이 소유한다. 대화/DB 전체 export나 worker 자동 시작을 하지 않는다.
- 사용자가 경험 저장을 요청한 경우만 현재 공식 save_memory 도구의 project/server·입력 schema·반환 ID를 확인한다. 실제 API가 sourceFingerprint를 지원하면 동일 요청 재전송에 같은 fingerprint를 재사용하고 정정은 새 근거로 구별한다. 미지원 필드를 만들어 넣지 않는다. 경험 관측을 확정 사실·작업 정본으로 승격하지 않는다.
- worker 시작/업데이트/백업은 여기서 하지 않는다. 연결 부재면 검색·저장을 미실행으로 알리고 사용자가 제공한 기존 자료만 활용한다.
- 별도로 MCP 준비·진단·worker 관리가 요청된 경우만 [Claude-Mem 실행기 연결](../../../../references/claude-mem.md)을 적용한다. 검색 연결과 수명 관리의 수행·완료를 구분한다.

### Wiki — 지식 조회와 변경

- 명시 Wiki 업무는 [wiki](../../../wiki/SKILL.md)에 연결한다. 단순 읽기는 공식 wiki-query, 수집·compile·수정·점검 실행은 선택 제품의 공식 관리 skill로 나눈다. 원본 보관·ingest·compile·검증은 각각의 결과를 확인한다.
- 조회 중 stale index를 발견해도 자동 재생성하거나 query log를 쓰지 않는다. 관리 기능에서 변경 효과가 필요하면 기존 승인과 대조한다.
- 실제 hub/topic·자료 소속·공유 범위를 확인한다. 회사 자료를 개인 hub에 저장하거나 로컬 미색인을 NAS fallback으로 처리하지 않는다. 자동 capture·feedback·초기 맥락 주입·private adapter 활성화는 별도 설정 작업이며 이 연결로 켜지지 않는다.
- 도구 부재 시 기존 허용 원본의 직접 조회와 미연결 상태를 제공한다. Wiki 정본을 대체하는 새 로컬 DB/카탈로그를 만들지 않는다.

### Zotero·organize — 선택 사용

- Zotero는 현재 설치된 공식 앱/API·실제 library·권한이 확인된 경우만 논문/서지 연결에 사용한다. 커넥터나 새 동기화·저장소를 자동 설치하지 않는다. 부재면 원본과 서지 포인터를 보존하고 미연결로 알린다.
- 반복 분류가 요청된 경우만 [files.md의 organize 실행](../types/files.md)을 적용한다. organize가 추출·검색·정본 결정까지 대신한다고 보지 않는다.

## 결과와 완료 판단

- 확인한 공식 대상·선택 범위·실제 호출과 반환 ID/경로·오류·미실행을 보고한다. 설치 경로 존재·wrapper resolve 성공은 실제 업무 실행 성공과 다르다.
- 저장은 대상에서 확인 가능한 결과와 대조한다. 실제 업무 완료·작업 기록·지식 반영·백업·전송은 별도 상태로 남긴다.
