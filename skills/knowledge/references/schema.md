# Knowledge repository schema

## Repository

```text
<knowledge-repository>/
├─ README.md
├─ index.md                   # 전체 content index, 자동생성
├─ log.md                     # 작업 이력, append-only
├─ sources/
│  ├─ index.md               # 자동생성
│  └─ <domain>/
│     ├─ <slug>.md           # inline source 또는 manifest
│     └─ <slug>/             # 선택적 repository payload
└─ wiki/
   ├─ index.md               # 자동생성
   ├─ inbox/                 # 미정리 seed
   └─ <domain>/
      ├─ index.md            # 자동생성 MOC
      └─ <slug>.md
```

도메인은 고정 목록이 아니다. 기존 도메인을 우선 쓰고 반복되는 새 주제가 생길 때 사람이 승인하면 추가한다.

## Source record

모든 원본은 qmd와 filesystem 검색이 읽을 수 있는 Markdown record를 하나 갖는다.

```yaml
---
kind: source
title: Example source
source_type: article
storage: inline
origin: https://example.com/article
captured: 2026-09-03
tags: []
# profile_key: extensions.example.knowledge.sources_root
# relative_path: books/example.pdf
# sha256: ...
# license: ...
---
```

필수 필드:

| 필드 | 의미 |
|---|---|
| `kind` | 항상 `source` |
| `title` | 사람이 식별할 제목 |
| `source_type` | `article`, `paper`, `experiment` 같은 열린 문자열 |
| `storage` | `inline`, `repository`, `external`, `remote` |
| `captured` | 이 record를 확보한 날짜 |

`origin`은 실제 출처가 있을 때 필수다. 직접 관찰·대화 기반이면 `source_type`으로 사실대로 표시하고 출처를 만들지 않는다.

| storage | payload |
|---|---|
| `inline` | record 본문에 불변 snapshot |
| `repository` | record 인접 상대경로에 Git 추적 |
| `external` | `profile_key`와 `relative_path`로 외부 위치 해석 |
| `remote` | `origin`의 원격 자료만 참조. 변경 가능성을 전제로 함 |

고정 크기 제한 대신 *“이 파일이 Git 이력에 영구히 남아도 안전하고 유용한가?”*로 판정한다. 대용량·바이너리·민감정보·복제 제한 자료는 외부에 두고 비민감 manifest만 추적한다. 실제 개인 경로·IP·secret은 record에 넣지 않는다.

Source payload는 수정하지 않는다. 정정본이나 새 판은 새 record로 추가하고 Wiki에서 관계를 설명한다. manifest의 오탈자·가용 상태를 고쳤다면 `log.md`에 남긴다.

## Wiki note

```yaml
---
kind: wiki
title: Example concept
summary: 한 줄 요약
tags: []
links: []
sources: []
status: seed
created: 2026-09-03
updated: 2026-09-03
# review: {next: 2026-09-10, interval: 7, score: 3}
---
```

| 필드 | 규칙 |
|---|---|
| `links` | 관련 Wiki note의 repository 상대경로 |
| `sources` | 근거 source record의 repository 상대경로 |
| `status` | `seed`, `evergreen`, `archived` |
| `review` | dive가 간격 반복을 관리할 때만 사용 |

- 중요한 주장 옆에는 본문 Markdown 링크로 근거를 표시한다.
- 출처 없는 빠른 캡처는 `sources: []`, `status: seed`로 허용한다.
- 상충하는 근거는 하나를 지우지 않고 `불확실성/충돌` 섹션에서 함께 연결한다.
- `evergreen`은 충분히 정리됐다는 뜻이지 영구히 참이라는 뜻이 아니다.
- 상대경로 Markdown 링크를 사용한다. 특정 viewer 전용 wikilink를 정본 문법으로 요구하지 않는다.

## Index와 log

- `index.md`는 내용 중심 탐색 문서다. generator가 title·summary·상태·링크로 재생성한다.
- `log.md`는 시간 중심 append-only 이력이다. 대화나 원문 전체를 복제하지 않는다.

```markdown
## [2026-09-03] ingest | Example source

- Updated: `wiki/dev/example.md`
- Result: 기존 설명에 새 근거와 충돌 항목을 추가함.
```

허용 operation은 `capture`, `ingest`, `query`, `lint`, `migrate`다.
