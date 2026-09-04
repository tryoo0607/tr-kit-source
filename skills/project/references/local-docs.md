# Project local-docs v2

## 하이브리드 모델

```text
sources -----------------------------+
                                     |
state ----완료----> exec -------------+--> wiki --> index
  |                     |             |              |
  +-- lifecycle 재개    +-- 작업 사실 +-- 근거       +-- query
```

- `state/`는 변경 중인 작업과 lifecycle hook 진입점이다.
- `exec/`는 완료된 작업 근거다.
- `sources/`는 외부 근거를 보존한다.
- `wiki/`는 현재 project 이해를 유지한다.
- `index.md`는 자동생성하고 `log.md`는 Wiki 유지보수를 기록한다.

Sources나 Wiki를 만들고 고치기 전에 plugin root `core/llm-wiki/`의 공통 schema와 operation을 읽는다.

## Routing

| 요청 | 먼저 읽을 것 | 다음 |
|---|---|---|
| “이 작업 이어가자” | 주입된 pointer 또는 선택한 `state/<slug>.md` | 필요할 때만 연결 Wiki·설계·결정 |
| “진행 중인 것 보여줘” | 생성 root index 또는 state 파일명 | 선택한 state |
| “이 프로젝트 구조가 뭐야” | `wiki/index.md`와 유지된 Wiki | 연결 source·work 근거 |
| “전에 뭘 했지” | `rg`로 `exec/` 후보 축소 | 일치 기록만 읽기 |
| 재사용 project 지식 보존 | 공통 Synthesize operation | Wiki 갱신 + `work_refs` |
| local-docs 점검 | 공통 linter `--project` | warning을 해석하되 추측 보정 금지 |

현재 session state 자체가 project 지식인 것은 아니다. 한 작업을 넘어 다시 쓸 구조·결정·운영·제약만 합성한다.

## 도구

이 스킬이 들어 있는 설치 plugin을 `<plugin-root>`, project skill directory를 `<skill>`로 해석한다.

```sh
python3 <plugin-root>/core/llm-wiki/scripts/llm_wiki_index.py --project <project-docs>
python3 <plugin-root>/core/llm-wiki/scripts/llm_wiki_index.py --project --check <project-docs>
python3 <plugin-root>/core/llm-wiki/scripts/llm_wiki_lint.py --project <project-docs>
python3 <skill>/scripts/local_docs_migrate.py <project-docs>          # dry-run
python3 <skill>/scripts/local_docs_migrate.py --apply <project-docs>  # 승인된 쓰기
```

migration은 project별로 실행한다. 사용자가 명시하지 않으면 `_docs`의 모든 child를 순회해 고치지 않는다.

## Retrieval

- lifecycle 질문은 semantic 검색이 아니라 state pointer와 직접 읽기를 사용한다.
- project 지식 질문은 Wiki를 먼저 읽고 `sources`와 `work_refs`로 확인한다.
- 과거 질문은 `rg`로 `exec/`를 찾으며 전체 원장을 읽지 않는다.
- qmd collection은 한 환경의 `_docs` root 하나를 포함할 수 있지만 semantic mask는 project `wiki/`와 `sources/` 중심으로 둔다. state·exec·out·생성 index는 제외한다.

## 저장 정책

| 환경 | 동작 |
|---|---|
| 개인/NAS | 기존 private local-docs backup과 승인된 push 정책 |
| 회사 | local-only, 회사 기록을 외부로 push하지 않음 |
| public kit | 계약과 도구만 배포하며 local-docs 데이터는 포함하지 않음 |

qmd index와 model은 모든 환경에서 머신 로컬 파생 데이터다.
