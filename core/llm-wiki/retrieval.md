# LLM Wiki 공통 검색

## Provider routing

```text
query
  ├─ healthy qmd collection ── qmd
  └─ 없거나 느림 ───────────── index + rg + direct read
                                      ↓
                             Wiki 우선, 근거 확인
```

qmd는 선택형 retrieval adapter다. Markdown과 Git이 정본이다.

## qmd

- knowledge repository 하나를 collection 하나로 둔다.
- local-docs 환경은 `_docs` root 하나를 collection으로 두고 여러 project Wiki를 함께 찾을 수 있다.
- `wiki/`에는 synthesis 우선 context, `sources/`에는 provenance context를 둔다.
- cache·사람용 산출물·lifecycle log·생성 index는 semantic 후보에서 제외한다. local-docs의 대표 제외 경로는 `*/state/**`, `*/exec/**`, `*/out/**`, `**/index.md`다.
- 결과가 Wiki인지 Sources인지 확인한 뒤 synthesis 또는 evidence로 사용한다.
- qmd database·embedding·model cache는 repository 밖에 둔다.
- 실제 MCP 연동 필요가 생길 때만 harness adapter를 추가한다.

full semantic query는 CPU에서 비쌀 수 있다. 지연이 중요하면 keyword search나 filesystem fallback을 우선한다.

## Filesystem fallback

1. root `index.md`에서 domain 또는 active state를 고른다.
2. domain index와 후보 note를 읽는다.
3. 정확 검색은 `rg`로 좁힌다.
4. 필요한 Wiki `links`, `sources`, project `work_refs`만 따라간다.
5. 유지된 Wiki에 없으면 inbox와 sources를 찾는다.

project 과거 이력은 `rg`로 `exec/` 후보를 좁혀 선택한 기록만 읽는다. work 원장 전체를 context에 넣지 않는다.

## 결과 우선순위

1. 직접 관련된 유지 Wiki note
2. 연결된 source 또는 완료 work 근거
3. retrieval이 추가로 찾은 source
4. 검증되지 않은 inbox seed 또는 mutable active state

검색 점수는 사실성 점수가 아니다. note 상태·근거·최신성·접근 가능성을 함께 판단한다.
