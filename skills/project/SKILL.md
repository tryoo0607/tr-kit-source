---
name: project
description: '`~/projects` 아래 project 공간과 local-docs·worktree·backup을 관리하고 프로젝트 지식을 조회·정리할 때 사용한다. "프로젝트 생성", "worktree", "local-docs", "전에 한 작업", "프로젝트 구조", "백업 연결". 코드 내용은 다루지 않는다.'
---

# project

프로젝트의 **공간(폴더·worktree)과 기록 인프라(`_local-docs`·백업·케이스)**를 관리한다.
**코드 내용엔 손대지 않는다** — 커밋·머지·브랜치 전략은 `git`.

> `_local-docs`에 **무엇을 어떤 형식으로 쓰는가**는 플러그인 루트의 **`LOCAL-DOCS-SCHEMA.md`**가 정본이다. 여긴 그 **바깥일**(자리를 만들고, 백업하고, 옮기는 일)을 한다.

local-docs v2는 plugin root의 `core/llm-wiki/` 공통 계약에 `state → exec` 작업 생명주기를 결합한다. 외부 근거는 `sources/`, 현재 project 지식은 `wiki/`에 두며 모든 작업 기록을 Wiki로 복제하지 않는다.

## 🔑 먼저 — 갈림선

| | 어디 |
|---|---|
| 프로젝트 시작 · 뼈대 | 아래 **구조** + `LOCAL-DOCS-SCHEMA.md` |
| 병렬 작업 공간 | `references/worktree.md` |
| `AGENTS.md` 배치 | `references/agents-md.md` |
| fork repo remote 구성 | `references/fork.md` |
| 백업이 안 돌 때 · 새 머신 | `references/backup.md` |
| 검증 케이스 원장 | `references/cases.md` |
| 스키마 마이그레이션 | `references/migrate.md` |
| 기록 재개·과거 작업·project 지식 조회·합성·점검 | `references/local-docs.md` + plugin root `core/llm-wiki/` |

## 구조

```
~/projects/
├─ _docs/<project>/          작업 기록 실파일 (백업됨)
├─ _assets/<project>/        대용량 원본 (백업 안 됨)
└─ <project>/
    ├─ _local-docs → ../_docs/<project>    심링크
    ├─ <repo>/                             코드 (자체 .git)
    └─ <repo>.worktrees/<slug>/            병렬작업
```

`_docs/<project>/` 내부 v2 구조는 [local-docs.md](references/local-docs.md)를 따른다. `state/`, `exec/`, `cases/`, `out/` 경로는 lifecycle hook 호환성을 위해 v1과 같다.

**예외 — bare 레이아웃**: 인프라·kit·유틸 repo는 중첩 없이 `~/projects/<repo>`가 곧 repo다.

> 🔑 **실파일이 프로젝트 밖에 있는 이유**: `git add -f`는 **중첩 git repo 안의 파일을 에러 없이 무시한다.** 안에 두면 그 프로젝트가 repo가 되는 순간 백업이 **조용히** 끊긴다. (실제로 끊겨 있었다 — `references/backup.md`)

## `_assets/` — 대용량 원본

`_docs/`의 형제다. meta-repo `.gitignore`가 `/*` + `!/_docs/`라 **자동으로 무시된다.**

성격이 다르면 다루는 법도 다르므로 셋으로 나눈다:

| | 무엇 | 주의 |
|---|---|---|
| `deploy/` | 기동 가능한 산출물 (jar·바이너리·인스턴스) | 🔑 **secret을 품기 쉽다** (키스토어·인증서) |
| `data/` | 적재용 데이터 (스키마·덤프·시드) | 재취득 가능한지 확인 |
| `refs/` | 읽기용 원본 (로그·증적·제공 자료) | 대개 **재취득 불가** → 지우면 끝 |

- **문서엔 결론과 핵심 발췌만** 쓰고 원본은 상대경로로 가리킨다. 폴더 slug를 문서 slug와 공유하면 `grep <slug>`로 양쪽이 잡힌다.
- **백업 대상이 아니다.** 재취득 불가 자료가 들어오면 그 사실을 적고 별도 백업이 필요한지 판단한다 — `_docs/`에 넣는 건 답이 아니다(용량).

### ⚠️ secret이 있으면 `chmod 700`

`~/projects`가 다른 계정에 **읽기전용 bind mount로 노출되는 구성**이면, ro는 **쓰기만 막고 읽기는 못 막는다.** 기본 755면 그 계정이 그대로 읽는다.

```sh
chmod 700 _assets/<project>/deploy
find _assets/<project>/deploy -type f -exec chmod 600 {} +
sudo -u <그계정> ls <노출경로>/deploy    # "허가 거부"여야 정상
```

## 경계

| 일 | 어디 |
|---|---|
| 커밋 · 머지 · rebase · PR · 브랜치 전략 | `git` — project는 worktree와 **딸린 브랜치를 낳기만** 한다 |
| 기록의 형식·스키마 | `LOCAL-DOCS-SCHEMA.md` |
| 무엇을 기록하나 | **백본** — 각 단계의 `returns` |
| kit 자체 설치·점검 | `kit` |
| project 밖에서도 재사용할 일반 지식 | `knowledge` |
