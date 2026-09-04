# Knowledge operations

## Capture

빠르게 남길 때는 흐름을 막지 않는다.

1. 재사용 가능한 내용인지 확인한다. 프로젝트 내부 상태면 local-docs로 돌린다.
2. `wiki/inbox/<slug>.md`에 `status: seed`로 저장한다.
3. 이미 근거가 있으면 source record를 먼저 연결한다.
4. 근거가 없으면 `sources: []`를 유지한다. 출처를 추측하지 않는다.
5. index를 재생성하고 변경 범위를 lint한다.

대화 중 자동 제안은 같은 내용에 한 번만, 한 줄로 한다. 롤오버나 세션 종료 sweep은 누락 후보가 있을 때만 제안한다.

## Ingest

1. 원본을 repository에 직접 둘지 외부 manifest로 둘지 schema의 혼합 보관 기준으로 판정한다.
2. source record를 만들고 payload를 확보한다. 기존 source payload를 요약본으로 덮어쓰지 않는다.
3. [retrieval.md](retrieval.md)에 따라 관련 Wiki를 찾는다.
4. 새 페이지보다 관련 기존 페이지 갱신을 우선한다.
5. source 연결, 중요한 주장 옆 근거 링크, 관련 Wiki 링크를 갱신한다.
6. 새 근거가 기존 주장과 충돌하면 양쪽 근거와 불확실성을 남긴다.
7. 별도 개념이 필요할 때만 새 Wiki note를 만든다.
8. index generator, deterministic lint 순으로 실행한다.
9. `log.md`에 ingest 한 건을 append한다.

한 source가 여러 페이지에 영향을 줄 수 있다. 변경 파일 수를 인위적으로 제한하지도, 관련 없는 페이지까지 채우지도 않는다.

## Query

1. retrieval provider로 Wiki 후보를 찾는다.
2. 후보 note와 명시된 `links`를 직접 읽는다.
3. Wiki를 우선 사용하고 주장 확인·빈틈 보완이 필요할 때 source record와 payload로 내려간다.
4. repository 상대 링크로 근거를 제시한다. 외부 payload에 접근하지 못하면 그 한계를 밝힌다.
5. Wiki에 없는 내용을 사실처럼 추론하지 않는다. 필요하면 새 source 조사 여부를 묻는다.
6. 질의에서 나온 재사용 가능한 새 synthesis는 자동 저장하지 않고 한 번 제안한다. 사용자가 승인하면 ingest 규칙으로 편입하고 `query` log를 남긴다.

읽기만 한 질의는 log를 강제하지 않는다. Wiki에 반영했거나 이후 유지보수에 의미 있는 경우에만 기록한다.

## Lint

먼저 `knowledge_lint.py`로 결정적 검사를 수행한다.

| 오류 | warning |
|---|---|
| 필수 frontmatter 누락 | 출처 없는 seed |
| 경로와 `kind` 불일치 | 다른 Wiki에서 연결되지 않은 note |
| 깨진 상대 링크·안전하지 않은 payload 경로 |  |
| 존재하지 않는 source 참조·출처 없는 evergreen |  |
| 자동생성 index drift |  |
| 잘못된 log header |  |

그다음 요청 또는 실제 필요가 있을 때만 LLM 의미 검사를 수행한다.

- 서로 충돌하거나 이미 대체된 주장
- 합쳐야 할 중복 페이지
- 빠진 교차 링크·개념 페이지
- source가 실제 주장을 뒷받침하는지
- 외부 payload에 현재 접근 가능한지
- 추가 조사가 필요한 지식 공백

자동 수정은 구조적으로 확실한 index에 한정한다. 의미가 달라질 수 있는 보정은 report-first로 제안한다.

## 실패와 중단

- qmd가 없거나 실패하면 filesystem fallback으로 계속한다.
- 외부 source가 없으면 Wiki만으로 가능한 범위와 근거 한계를 밝힌다.
- 답의 필수 근거가 접근 불가하면 추측하지 말고 중단해 사용자에게 알린다.
- schema가 다른 legacy repository는 자동 이동하지 않고 migration dry-run을 먼저 제시한다.
