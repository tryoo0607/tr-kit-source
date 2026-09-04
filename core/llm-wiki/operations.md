# LLM Wiki 공통 동작

## Capture

1. 이 저장소에 속하는 내용인지 판정한다.
2. `wiki/inbox/<slug>.md`에 최소 seed를 쓴다.
3. 기존 근거가 있으면 source record를 연결하고 없으면 `sources: []`를 유지한다.
4. index를 재생성하고 변경 저장소를 lint한다.

현재 작업을 막지 않도록 제안은 한 번만 한다. 출처를 만들어내지 않는다.

## Ingest

1. [schema.md](schema.md)의 혼합 보관 기준으로 repository와 external storage를 고른다.
2. source record와 payload를 요약본으로 덮어쓰지 않고 보존한다.
3. 새 페이지를 만들기 전에 관련 Wiki를 찾는다.
4. 기존 synthesis·source link·교차 link·충돌 설명을 갱신한다.
5. 별도 개념일 때만 새 Wiki note를 만든다.
6. index 생성, deterministic lint, log append 순으로 끝낸다.

한 source가 여러 Wiki에 영향을 줄 수 있다. 관련된 문서는 모두 고치되 변경 범위를 임의로 넓히지 않는다.

## Project work synthesis

project mode는 work에서 Wiki로 이어지는 경로를 추가한다.

1. 관련 `state/` 또는 `exec/`를 완료하거나 읽는다.
2. 결과가 그 작업을 넘어 다시 쓰일지 판정한다.
3. 새 note보다 기존 project Wiki 갱신을 우선한다.
4. 안정적인 work 근거를 `work_refs`로 연결한다. 작업이 끝났으면 `exec/`를 우선한다.
5. 작업 로그 전체를 Wiki에 복제하지 않는다.
6. project index·lint와 `synthesize` log로 끝낸다.

## Query

1. Wiki 후보를 찾는다.
2. 후보와 명시된 `links`를 직접 읽는다.
3. 중요한 주장은 `sources`로, project mode에서는 필요한 `work_refs`까지 확인한다.
4. 외부 payload나 work 근거에 접근할 수 없으면 한계를 밝힌다.
5. 없는 내용을 기록된 사실처럼 추론하지 않는다.
6. 질의 중 생긴 재사용 가능한 synthesis는 한 번 저장을 제안하되 자동으로 Wiki를 바꾸지 않는다.

읽기만 한 query는 log를 강제하지 않는다.

## Lint

결정적 linter를 먼저 실행한다.

| error | warning |
|---|---|
| 필수 frontmatter 누락 | 출처 없는 seed |
| 경로와 `kind` 불일치 | orphan Wiki note |
| 깨지거나 탈출하는 상대 링크 | evergreen project Wiki가 mutable state 참조 |
| 존재하지 않는 source·work reference | legacy state metadata drift |
| 출처 없는 evergreen | 완료 의심 기록이 `state/`에 남음 |
| 자동생성 index drift | `_unrecorded.md` marker |
| 잘못된 log header | deprecated README 동적 필드 |

의미 판단이 필요할 때만 LLM 검사를 한다. 대상은 충돌 주장, 중복 페이지, 빠진 개념, 근거 품질, 외부 payload 접근성이다.

자동 보정은 생성 index처럼 구조적으로 확실한 항목에 한정한다. 의미가 달라질 수 있는 변경은 report-first다.

## 실패와 fallback

- qmd가 없거나 느리면 index, `rg`, 직접 읽기로 전환한다.
- 필수 근거에 접근할 수 없으면 한계를 밝히고 추측하지 않는다.
- legacy 저장소는 migration dry-run을 먼저 실행한다.
- project work 저장소는 환경의 저장 정책을 따르며 common core가 remote를 선택하거나 push하지 않는다.
