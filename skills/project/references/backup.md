# 백업 — meta-repo

`~/projects` 자체가 git repo(**meta-repo**)가 되어 `_docs/`를 개인 GitHub private repo(`local-docs`)에 push한다.
실행 도구 = `setup/bin/local-docs-backup`.

## ⛔ 개인 머신에서만

**회사 머신에는 붙이지 않는다.** *"백업 붙여줘"*라고 해도 붙이지 말고 이유를 설명하고 로컬 유지를 안내한다.

`local-docs-backup`은 meta-repo가 없으면 에러가 아니라 **정상 스킵(exit 0)**한다 — 회사에서 백업이 안 도는 건 **버그가 아니다.**

## 🔑 왜 `_docs/`가 프로젝트 밖에 있나 (버그 이력)

옛 구조는 `<project>/_local-docs/`가 실파일이고, 프로젝트 repo의 `.gitignore`를 `git add -f`로 뚫는 방식이었다. **그게 안 됐다:**

> `git add -f`는 **중첩된 git repo 안의 파일을 에러 없이 조용히 무시한다.**

그래서 repo가 아닌 프로젝트만 백업되고, **repo인 프로젝트의 기록은 통째로 백업 밖**이었다(2026-08-06 실측 — `{{KIT_REPO}}`의 재설계 문서 전부가 빠져 있었다).

v1은 실파일을 `~/projects/_docs/`로 빼서 **버그의 근원을 없앴다.** `.gitignore`가 단순해지고 `git add -f` 자체가 불필요하다:

```gitignore
/*
!/_docs/
```

## 진단

```sh
ls -d ~/projects/.git                      # ① meta-repo 연결됐나
crontab -l | grep local-docs-backup        # ② 자동 실행 등록됐나
command -v local-docs-backup               # ③ bin 설치됐나
local-docs-backup                          # ④ 실제로 돌려보기
ls -l ~/projects/*/_local-docs             # ⑤ 심링크 살아있나
```

| 증상 | 원인 | 조치 |
|---|---|---|
| `meta-repo 미연결 — 백업 스킵` | ① | 개인 머신이면 아래 **연결**. 회사면 **정상** |
| 명령 없음 | ③ | `setup/tools/install.sh` |
| 조용히 오래 안 돌았음 | ② | 아래 **cron** |
| `push 실패` | 원격·충돌 | fail-loud 설계. `git -C ~/projects status` |
| 심링크 깨짐 | ⑤ | 재생성. **시스템은 안 멈춘다** — 훅은 `_docs/`를 계산해 접근하므로 사람이 `ls`로 못 볼 뿐이다 |

> 🔑 **①과 ②를 둘 다 본다.** 하나만 되어 있으면 *"설치했으니 되겠지"*로 착각한다 — 실제로 bin만 깔리고 cron이 빠져 백업이 **0회**였던 사례가 있다.

## 연결 (새 개인 머신 · 유실 복구)

```sh
cd ~/projects
git init -b main
git remote add origin git@github.com:<me>/local-docs.git
git fetch origin
git reset origin/main          # 이력은 받되 작업트리는 보존
local-docs-backup              # 첫 백업
```

- ⚠️ **`git clone` 금지** — 이미 프로젝트들이 들어 있는 디렉토리다. `init` + `fetch` + `reset`으로 붙인다.
- ⚠️ **`reset --hard` 금지** — 작업트리(프로젝트 repo 전부)를 날린다.
- 붙인 뒤 `git -C ~/projects status`로 프로젝트 repo들이 스테이징에 안 딸려오는지 확인한다.

## cron

```sh
( crontab -l 2>/dev/null; echo "0 21 * * * $HOME/.local/bin/local-docs-backup >> $HOME/.local/state/local-docs-backup.log 2>&1" ) | crontab -
crontab -l | grep local-docs-backup      # 🔑 이 확인까지 해야 끝
```

「마무리」에서도 트리거된다. cron은 그 보강이다.

## 대상이 아닌 것

- **`_assets/`** — 용량. `.gitignore`가 `/*`로 이미 무시한다.
- **프로젝트 repo의 코드** — 각자 자기 원격이 있다.
