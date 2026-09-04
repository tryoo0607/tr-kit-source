# `_local-docs` 스키마 마이그레이션

v2는 plugin root의 LLM Wiki common core에 기존 top-level `state/`, `exec/`, `cases/`,
`out/` 작업 계층을 결합한다. 한 project씩 기본 dry-run으로 적용한다.

```sh
python3 <project-skill>/scripts/local_docs_migrate.py <project-docs>
python3 <project-skill>/scripts/local_docs_migrate.py --apply <project-docs>
```

**기계가 할 수 있는 건 스크립트가, 판단은 사람이.** 섞으면 둘 다 나빠진다 — 기계적인 걸 프롬프트로 매번 지시하면 조금씩 다르게 실행되고, 판단분을 스크립트에 욱여넣으면 틀린 자동화가 된다.

| | 무엇 |
|---|---|
| 🤖 `project/scripts/local_docs_migrate.py` | v2 sources/wiki/log/index 생성 · README 보정 · legacy 후보 보고. **dry-run 기본·멱등** |
| 👤 여기 | `design/`·`decisions.md`를 선별해 frontmatter를 갖춘 Wiki로 합성 |

🔑 **회사 머신에서 따로 돌려야 한다** — `_local-docs`는 push하지 않으므로 동기화가 없다. 각 머신에서 한 번씩.

## 절차

1. **먼저 확인한다** — 대상 프로젝트, 현재 스키마 버전(`README.md`), meta-repo 연결 여부.
2. **스크립트 실행** → 기계적인 부분이 끝난다. 결과를 `git status`로 확인한다(`git mv`라 이력이 보존돼야 한다).
3. **판단분을 묻는다** (아래).
4. **`README.md`의 스키마 버전을 올린다** — 이걸 빼먹으면 다음에 또 돈다.

## v0 → v1 판단분

### ① `explore/`·`research/`의 각 문서는 어디로?

| 성격 | 어디 |
|---|---|
| **한 작업**을 위한 조사 | `exec/<slug>.md` — 그 작업 기록에 녹인다 |
| **여러 작업에 걸친** 배경·설계 | `design/<주제>/` |

문서 하나하나 물어본다. *"이 조사, 그 작업 끝나면 다시 볼 일이 있나?"*가 갈림선이다.

### ② `INDEX.md`에 살릴 내용이 있나?

폐기하지만 **본문에 목록 이상의 것**(경위·판단·링크 모음)이 섞여 있을 수 있다. 있으면 `README.md`나 해당 `design/` 문서로 옮기고 제거한다.

### ③ 번호 접두 평면 문서 (`01-…`·`02-…`)

`touch-cc`식 배치다. 대부분 **작업 기록이 아니라 설계**라 `design/<주제>/`로 간다 — 하지만 개별로 확인한다.

## 끝나고

- `_local-docs` 심링크가 살아있는지 확인 (`ls -l`).
- `_docs` Git 작업 트리에서 변경이 추적되는지 확인하고, 개인 저장소라면 commit·push까지 검증한다 — **v0에서 `{{KIT_REPO}}` 기록이 조용히 빠져 있었다**(`backup.md`).
- lazy가 기본이라 **손 안 댄 프로젝트는 그냥 둬도 된다.** 섞여 있는 게 정상이다.
