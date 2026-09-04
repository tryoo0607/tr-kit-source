# Knowledge retrieval

## Provider 선택

```text
query
  ├─ qmd 사용 가능 + collection healthy ── qmd
  └─ 그 외 ────────────────────────────── index + rg + direct read
                         ↓
               Wiki 우선, Sources 검증
```

qmd는 선택형 retrieval adapter다. Markdown/Git 정본을 대체하지 않으며 설치·MCP 연결을 skill의 필수 조건으로 만들지 않는다.

## qmd

- knowledge repository root 전체를 collection 하나로 등록한다.
- `wiki/` context는 “LLM이 유지하는 지식, 일반 질의에서 우선”으로 둔다.
- `sources/` context는 “불변 근거, 검증과 ingest에 사용”으로 둔다.
- collection의 `ignore`에는 `tmp/**`, `output/**`처럼 repository 안에 남아 있는 작업 캐시·산출물 경로를 명시한다. Git ignore가 qmd에도 자동 적용된다고 가정하지 않는다.
- 일반 질의는 `qmd query`를 사용하고 결과 경로가 `wiki/`인지 `sources/`인지 확인한다.
- qmd database·embedding·model cache는 repository 밖의 파생 상태다. Git에 추가하지 않는다.
- CLI를 공통 경로로 사용한다. 향후 harness별 MCP 자동 연결이 실제로 필요할 때만 adapter로 분리한다.

공식 사용법과 설치 방식은 <https://github.com/tobi/qmd>를 확인한다. 도구 버전에 따라 달라질 수 있는 설치 명령이나 내부 모델 이름을 skill에 복제하지 않는다.

## Filesystem fallback

1. root `index.md`에서 관련 domain을 좁힌다.
2. `wiki/<domain>/index.md`와 후보 note를 직접 읽는다.
3. 정확 검색은 repository root에서 `rg`를 사용한다.
4. Wiki의 `links`와 `sources`를 따라 필요한 파일만 읽는다.
5. 찾지 못하면 `wiki/inbox/`, 그다음 `sources/`를 검색한다.

index가 없거나 drift 상태면 `knowledge_index.py --check`로 확인한다. 쓰기 권한과 사용자 의도가 있을 때만 재생성하고, 읽기 요청 때문에 repository를 임의 수정하지 않는다.

## 결과 우선순위

1. 질의와 직접 관련된 Wiki note
2. Wiki에서 연결한 source record
3. qmd가 추가로 찾은 source
4. 출처 없는 inbox seed

검색 순위는 사실성 순위가 아니다. 최종 답은 note의 상태·근거·최신성과 source 접근 여부를 함께 판단한다.
