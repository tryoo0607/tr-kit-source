---
name: knowledge
description: 재사용 지식을 Markdown LLM Wiki에 축적·조회·정리할 때 사용한다. "지식으로 남겨", "전에 기록한 것 찾아줘", "지식베이스 점검해줘".
---

# knowledge

이 스킬은 LLM Wiki 방법론을 제공한다. 저장소는 plugin root의 `profile/setup.py get public.repositories.knowledge`로 해석한다. 미설정이면 읽기·쓰기 전에 `profile-setup`으로 연결하며 경로나 remote를 추측하지 않는다.

## 핵심 계약

- 공통 schema·operation·retrieval·도구는 plugin root의 `core/llm-wiki/`가 정본이다.
- `sources/`는 근거 정본이다. LLM은 읽고 ingest하지만 원본 payload를 고쳐 쓰지 않는다.
- `wiki/`는 현재 지식 정본이다. LLM이 sources를 누적 종합하고 링크·충돌·최신 상태를 유지한다.
- 같은 repository 전체가 하나의 탐색 공간이다. qmd·Obsidian은 선택 사항이며 Markdown과 Git이 정본이다.
- 프로젝트 밖에서도 재사용할 지식만 여기에 둔다. 프로젝트 내부 상태·결정은 project local-docs에 두고 중복하지 않는다.
- source를 읽지 못했거나 근거가 없으면 꾸며내지 말고 `seed` 또는 접근 불가로 표시한다.

## 활동

| 요청 | 수행 전 읽을 문서 |
|---|---|
| 빠른 캡처·자료 추가·기존 지식 통합 | [operations.md](../../core/llm-wiki/operations.md)의 Capture·Ingest + [schema.md](../../core/llm-wiki/schema.md) |
| 기존 지식 조회·질문 | [operations.md](../../core/llm-wiki/operations.md)의 Query + [retrieval.md](../../core/llm-wiki/retrieval.md) |
| 링크·출처·모순·오래된 내용 점검 | [operations.md](../../core/llm-wiki/operations.md)의 Lint + [schema.md](../../core/llm-wiki/schema.md) |
| repository 초기화·구조 변경 | [schema.md](../../core/llm-wiki/schema.md) 전체 |

새 source를 별도 노트로 요약하는 데서 멈추지 않는다. 관련 Wiki를 먼저 찾아 기존 페이지·교차 링크·충돌 표시를 갱신하고, 새 페이지는 별도 개념이 필요할 때만 만든다.

## 결정적 도구

설치된 plugin root를 `<plugin-root>`라 할 때:

```sh
python3 <plugin-root>/core/llm-wiki/scripts/llm_wiki_index.py <knowledge-repository>
python3 <plugin-root>/core/llm-wiki/scripts/llm_wiki_index.py --check <knowledge-repository>
python3 <plugin-root>/core/llm-wiki/scripts/llm_wiki_lint.py <knowledge-repository>
```

- index는 손으로 동기화하지 않는다. 저장·이동 후 generator를 실행한다.
- lint 오류는 고친 뒤 커밋한다. warning은 의미 검사의 입력이며 사실처럼 자동 보정하지 않는다.
- 지식 저장 후 knowledge repository에 한 줄 Conventional Commit을 만든다. push는 사용자 확인 후 수행한다.
