# 외부 기록 도구 연결

종류별 절차에서 실제 외부 조회나 반영이 필요할 때 해당 도구 절만 읽는다. 공통 입력과 실패 기준은 함께 적용한다. 설치나 제품 내부 절차를 복제하지 않는다.

## 입력과 전제

실제 설치본의 식별자, 버전, 도구나 SKILL.md 위치와 사용 허용을 확인한다. 문서에 이름을 적은 것을 자동 호출이나 연결 완료로 취급하지 않는다. 아래는 원본 검토로 확인한 연결 범위이며, 특정 호스트에서의 실행 검증을 대신하지 않는다.

## 수행 방법과 절차

조립본에는 [BMAD](../../../bmad/SKILL.md), [경험 검색](../../../mem-search/SKILL.md), [Wiki](WIKI_SKILL_ENTRY)가 포함된다. 이 링크는 제품별 조립 후 유효하다. 각 원본은 dependencies.toml의 commit으로 고정하며 assembly.json에서 실제 포함을 확인한다.

### 실행 연결

`<plugin-root>`는 현재 조립본 위치다. 아래 실행기는 원본 도구를 호출하며 자체 기록 DB를 만들지 않는다. 최초 사용 전 `python3 <plugin-root>/scripts/records.py doctor`로 파일과 uv/Bun/Node를 확인한다. 설치나 hook 등록은 수행하지 않는다.

- BMAD 초기화/확인: `python3 <plugin-root>/scripts/records.py bmad-setup --project-root <project>`를 사용한다. 최초 질문과 승인, `--module-answers`는 BMAD setup 지침을 따른다. 상태만 확인하려면 `--status`를 추가한다.
- Wiki 로컬 검사: `python3 <plugin-root>/scripts/records.py wiki --help`로 제공 기능을 확인한다. 자료 수집과 지식 합성은 Wiki skill을 적용하며 로컬 helper가 LLM 합성을 대신한다고 보지 않는다.
- 세션 기록: `python3 <plugin-root>/scripts/records.py wiki-session --hub <hub> capture --help`로 명시 수집 입력을 확인한다. 실제 허브 범위를 지정해 capture/rehydrate를 사용한다.
- Claude-Mem: uv와 별개로 Bun이 필요하다. 확인한 데이터 경로와 포트로 upstream worker를 명시적으로 실행한다. `python3 <plugin-root>/scripts/records.py mem-worker --daemon`은 상시 서비스 시작이므로 해당 실행 범위를 확인한다. 플러그인 MCP는 `mem-mcp`를 연결하지만 worker를 자동 시작하지 않는다. worker 부재를 빈 검색 결과로 취급하지 않는다.

### BMAD 작업 기록

계획과 티켓에서 상태, 요구, 검증과 다음 행동을 조회한다. 기록 갱신은 확인한 BMAD 설치본의 해당 기능을 사용하며, 조회나 인계 요청만으로 build를 시작하지 않는다. 외부 기록과 현재 작업이 충돌하면 작업 정본의 요구와 사용자 정정을 대조한다.

### Claude-Mem 경험

검색에서 프로젝트와 질문으로 후보를 좁히고 필요한 시간대와 상세 관측만 조회한다. 확인한 인터페이스가 제공하는 ID와 원래 근거를 보존한다. 내보내기가 필요할 때만 대상 범위를 정하며 전체 DB를 기본 복사하지 않는다. 관측 자동 수집의 설정/실행은 이 skill이 맡지 않는다.

worker MCP의 `save_memory`로 명시적인 결정, 정정이나 인계 메모를 남길 수 있다. 먼저 관련 기록을 검색하고 `text`, `title`, `project`, 출처 metadata를 전달한 뒤 반환 ID를 확인한다. 동일 근거의 재전송에는 원본 위치와 revision/내용을 식별하는 `metadata.sourceFingerprint`를 재사용할 수 있다. 내용이 달라진 정정에는 새 fingerprint와 이전 근거 연결을 사용한다. 같은 fingerprint의 변경 내용은 upstream이 중복으로 처리하므로 덮어쓰기에 사용하지 않는다. 검색은 `search`, `timeline`, `get_observations`의 원본 절차를 따른다. 저장 메모를 BMAD 상태의 사본이나 Wiki의 확정 지식으로 취급하지 않는다.

export/import는 Claude-Mem 간 자료 전달용이다. Claude Code auto-memory를 받는 memory-ingest를 BMAD나 Wiki의 범용 importer로 사용하지 않는다. Wiki 내용을 Claude-Mem에 계속 역복제하지 않고 필요한 지식은 원래 Wiki에서 조회한다.

### LLM Wiki 지식과 세션

확인한 Wiki skill의 요청별 절차로 진입한다. 자료 저장은 ingest, 지식 정리는 compile/update, 조회는 query, 세션 맥락은 session capture/rehydrate에 해당하는 실제 지원 기능을 선택한다. 자료 수집과 지식 합성, 세션 기록을 구분하고 원본의 경로와 메타데이터를 따른다.

BMAD 기록이나 Claude-Mem 결과를 넘길 때 원래 식별자/위치, 확인 시점과 범위, 검증과 미확인을 함께 전달한다. 기존 출처와 관련 지식을 먼저 찾아 재처리를 중복 생성으로 만들지 않는다. 세션 digest는 작업 정본이나 검증된 지식이 아니며, 필요한 내용만 명시적으로 지식에 반영한다.

## 연계와 의존

| 대상과 요청 | 입력 | 필요한 결과 | 의존과 부재 시 동작 |
|---|---|---|---|
| BMAD 설치본: 작업 기록 조회/갱신 | 작업 포인터, 조회 질문 또는 검증된 변경과 사용자 정정 | 실제 기록 위치, 상태와 미결, 반영 결과 | BMAD 기록 변경에 필수. 도구 부재 시 접근 가능한 기존 파일 조회만 하고 원본 형식을 추측해 생성하지 않음 |
| Claude-Mem 검색 또는 export | 프로젝트 범위, 관련 질문/시간대, 필요한 후보 ID | 관측과 근거, 검색 범위/한계 | 경험 조회에 선택. 부재 시 BMAD/Wiki의 접근 가능한 근거를 사용하고 memory 조회 미실행 표시. 실행 실패로 범위를 확대하지 않음 |
| nvk/llm-wiki: 지식 조회/반영 또는 세션 맥락 | 대상 Wiki/세션, 자료와 출처, 요청 동작과 보관 범위 | 실제 source/지식/digest 위치, 반영 또는 조회 결과와 미결 | Wiki 쓰기에 필수. 부재 시 접근 가능한 기존 파일 조회와 후보 정리까지만 하고 미반영 표시 |

외부 skill은 현재 설치본의 SKILL.md로 진입해 공통 제약과 해당 분기를 따른다. 실제 도구는 그 버전의 지원 인터페이스를 확인해 사용한다. 사용하지 않을 도구 본문은 읽지 않으며, 별도 모델 호출이나 격리 실행을 보장하지 않는다.

## 결과와 완료 판단

원본 검토 근거는 BMAD 공식 build/review 문서, Claude-Mem search/export 문서, nvk/llm-wiki ingestion/session 지침이다. 실제 적용 시 사용할 설치본과 검증 범위를 확인한다. 파일 접근 확인, 저장 결과, 모델의 선택과 재개 성공은 각각 구분한다.

## 실패와 복구

부재/접근 불가/부분 검색을 빈 결과나 완료로 보고하지 않는다. 쓰기 실패는 실제 반영 위치를 다시 조회해 남은 부분만 처리한다. 기존 source, 지식과 작업 기록을 보존하고 임의 저장소나 대체 스키마를 만들지 않는다. 설치, 권한 확대와 원격 전송으로 자동 복구하지 않는다.
