# fork repo 규약

오픈소스 fork를 받아 작업할 때의 remote 구성과 전환 절차.

## 규약 — 클론 1개 + remote 2개

```
origin   = 내 fork    (push 대상, 여기서 작업·커밋)
upstream = 원본       (fetch 전용)
```

`gh repo fork --remote`가 만드는 표준 구성이다. 클론을 2벌 두지 않는다 — 오브젝트 저장소가 통째로 중복된다.

**디렉토리 이름 = upstream repo 이름 그대로.** fork라는 사실은 remote 구성이 말한다.
`<repo>-<내계정>` 같은 접미사 금지 — 같은 fork를 원본과 fork로 오인하게 만들 수 있다. 디렉토리명은 upstream repository 이름을 유지하고 remote로 소유권을 구분한다.

**upstream push 차단**:
```sh
git remote set-url --push upstream DISABLED
```

**최신화**:
```sh
git fetch upstream && git rebase upstream/main
```

**원본 트리를 통째로 펼쳐 봐야 할 때만 worktree** — 편집용이 아니라 열람·대조·버전스냅샷용이다.
```sh
git worktree add ../<repo>.worktrees/upstream-main upstream/main
git worktree add ../<repo>.worktrees/v0.12.1 v0.12.1
```
대개는 `git show upstream/main:<path>` / `git diff upstream/main`으로 충분하다.

**같은 repo가 여러 project에 필요하면 project별로 각각 클론**한다(project 경계 우선, .git 중복은 감수).

## 원본만 클론했다가 fork로 전환

**재클론 불필요** — 오브젝트는 이미 로컬에 있고, fork는 GitHub에서 원본의 복사본으로 만들어져 히스토리가 같다. remote만 재배치하면 기존 커밋이 그대로 새 origin으로 올라간다.

```sh
gh repo fork <owner>/<repo> --clone=false --remote=false   # 1) fork 생성
git remote rename origin upstream                          # 2) 재배치
git remote add origin https://github.com/<me>/<repo>.git
git remote set-url --push upstream DISABLED
git fetch origin
git branch -u origin/<branch> <branch>                     # 3) ⚠️ 필수
```

### ⚠️ 3번을 빼먹으면 사고

`git remote rename origin upstream`은 **로컬 브랜치의 추적 설정까지 따라 바꾼다** — `branch.<b>.remote`가 `origin` → `upstream`이 된다.

그래서 재배치 직후 무심코 `git push`하면 **내 fork가 아니라 원본으로 push를 시도한다.** 권한이 있는 repo면 원본에 직접 밀어버린다.

`--push upstream DISABLED`가 이 사고의 안전망이다 — 3번을 빼먹어도 push가 실패하고 끝난다. 규약에 push 차단이 들어간 이유가 이것.

**검증**:
```sh
git remote -v                    # origin=내 fork, upstream=원본(push=DISABLED)
git config branch.<b>.remote     # origin 이어야 함
```

## 점검 — fork 상태 자동 감지

내 fork 목록을 부모까지 한 번에 뽑아 로컬 origin과 대조한다.

```sh
gh repo list <me> --fork --limit 100 --json name,parent \
  --jq '.[] | "\(.parent.owner.login)/\(.parent.name) -> \(.name)"'
```

| 관측 | 판정 |
|---|---|
| origin=원본인데 내 fork가 GitHub에 있음 | **전환 후보** — 위 절차 |
| origin=내 fork인데 `upstream` remote 없음 | **누락 보정** — `git remote add upstream <원본>` |
| origin=남의 fork | **의도 확인** — 팀 fork 협업일 수 있다 |

세 번째는 실사례가 있다. `cb-spider`의 origin이 `ish-hcc/cb-spider`(남의 fork)였는데, 본인 커밋이 이미 push돼 있어 **팀 fork에서 협업하는 3단 구조**였다(원본 → 팀 fork → 내 작업). 잘못 물린 게 아니었으므로 origin은 그대로 두고 upstream만 추가하면 된다. **origin이 낯설다고 바로 고치지 말고 커밋 author와 push 상태를 먼저 볼 것.**

## 브랜치가 원격에서 사라졌을 때

로컬 원격추적 ref는 prune 전까지 남아 있어서 `git rev-list @{u}..HEAD`가 **0을 반환한다** — "미푸시 없음"으로 착각하기 쉽다. 삭제 전에는 **모든 원격**과 대조한다.

```sh
git rev-list --count <branch> --not --remotes=<r1> --remotes=<r2>   # 0이면 로컬 전용 커밋 없음
```

`feature/*` 브랜치가 원격 목록에 없는 건 대개 **머지 후 정리**된 것이다. 커밋이 `master`/`main`에 들어가 있는지 먼저 확인한다.
