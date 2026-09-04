# LLM Wiki 공통 스키마

## 공통 저장소

```text
<repository>/
├─ README.md
├─ index.md                   # 자동생성 content router
├─ log.md                     # append-only 유지보수 이력
├─ sources/
│  ├─ index.md               # 자동생성
│  └─ <domain>/
│     ├─ <slug>.md           # inline source 또는 manifest
│     └─ <slug>/             # 선택적 repository payload
└─ wiki/
   ├─ index.md               # 자동생성
   ├─ inbox/
   └─ <domain>/
      ├─ index.md            # 자동생성 MOC
      └─ <slug>.md
```

domain은 고정 taxonomy가 아니다. 기존 domain을 우선 사용하고 반복되는 주제에 안정적인 경계가 필요할 때만 추가한다.

project local-docs는 lifecycle 경로를 이동하지 않고 공통 저장소를 확장한다.

```text
<project-docs>/
├─ state/                     # 진행 중 작업, lifecycle hook 진입점
├─ exec/                      # 완료된 작업 기록
├─ cases/                     # 검증 case 원장
└─ out/                       # 사람용 산출물
```

## Source record

모든 원본은 검색 가능한 Markdown record를 하나 갖는다.

```yaml
---
kind: source
title: Example source
source_type: article
storage: inline
origin: https://example.com/article
captured: 2026-09-03
tags: []
# profile_key: extensions.example.sources_root
# relative_path: books/example.pdf
# sha256: ...
# license: ...
---
```

필수 필드는 `kind`, `title`, `source_type`, `storage`, `captured`다.

| storage | payload |
|---|---|
| `inline` | record 본문의 불변 snapshot |
| `repository` | record 옆의 Git 추적 payload |
| `external` | `profile_key`와 안전한 `relative_path`로 해석하는 위치 |
| `remote` | `origin`으로 참조하는 변경 가능한 원격 자료 |

고정 크기 임계값 대신 “Git 이력에 영구 보존해도 안전하고 유용한가?”로 판단한다. 대용량·바이너리·민감·재배포 제한 자료는 밖에 두고 비민감 manifest만 추적한다. 공개 record에 실제 개인 경로·IP·secret을 넣지 않는다.

source payload는 불변이다. 정정본·새 판은 새 record로 추가하고 관계는 Wiki에서 설명한다. manifest의 가용 상태나 오탈자를 고치면 `log.md`에 남긴다.

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
# work_refs: [exec/example.md]  # project 확장 전용
# review: {next: 2026-09-10, interval: 7, score: 3}
---
```

| 필드 | 규칙 |
|---|---|
| `links` | 관련 Wiki note의 repository 상대경로 |
| `sources` | source record의 repository 상대경로 |
| `status` | `seed`, `evergreen`, `archived` |
| `work_refs` | project에서만 쓰는 `state/`·`exec/` 근거 |
| `review` | 학습 workflow가 소유하는 선택적 간격반복 상태 |

- 중요한 주장 옆에 근거 링크를 둔다.
- 근거 없는 빠른 캡처는 `sources: []`, `status: seed`로 둔다.
- 충돌하는 근거를 지우지 말고 불확실성을 설명한다.
- `evergreen`은 충분히 유지된 상태이지 영원히 참이라는 뜻이 아니다.
- viewer 종속 wikilink가 아니라 상대경로 Markdown 링크를 정본 문법으로 쓴다.
- evergreen project Wiki는 변경 중인 `state/`보다 완료된 `exec/`를 우선 근거로 삼는다.

## Index와 log

`index.md`는 source와 Wiki metadata로 생성한다. project mode에서는 active state 표도 포함하되 work record 본문을 복제하지 않는다.

`log.md`는 대화·원문 전체가 아니라 실제 유지보수 이력만 append한다.

```markdown
## [2026-09-03] ingest | Example source

- Updated: `wiki/dev/example.md`
- Result: 새 근거와 충돌 설명을 추가함.
```

허용 operation은 `capture`, `ingest`, `synthesize`, `query`, `lint`, `migrate`다.
