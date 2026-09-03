---
description: 프로젝트의 `_local-docs` 자리를 만든다 (v1 스키마 — 실파일은 `~/projects/_docs/`, 프로젝트엔 심링크)
argument-hint: "[프로젝트명] (생략 시 현재 위치 기준)"
---

`LOCAL-DOCS-SCHEMA.md`(v1) 규약대로 작업 기록 자리를 만든다.

대상: `$ARGUMENTS` (비면 cwd에서 추정).

## 절차

1. **레이아웃 판정** — bare(`~/projects/<repo>` = kit·인프라·유틸)인지, 중첩(`~/projects/<project>/<repo>` = 코드 작업 프로젝트)인지.

2. 🔑 **실파일은 프로젝트 밖에** — `~/projects/_docs/<project>/`. 프로젝트 안엔 심링크만:
   ```sh
   mkdir -p ~/projects/_docs/<project>
   ln -s ../_docs/<project> ~/projects/<project>/_local-docs     # 중첩이면 경로 조정
   ```
   *`git add -f`는 중첩 git repo 안의 파일을 조용히 무시한다 — 안에 두면 백업이 끊긴다.*

3. **프로젝트 `.gitignore`에 `_local-docs/` 추가** (심링크가 커밋되지 않게).

4. **`README.md`만 만든다** — 나머지는 빈 폴더로 미리 파지 않는다:
   ```markdown
   # <project>

   | 스키마 | v1 |
   | 현재 초점 | … |
   | 다음 | … |
   ```

5. **나머지는 필요해질 때** — `state/` `exec/` `design/` `out/` `cases/` `decisions.md` `INBOX.md`. 첫 문서와 함께 생긴다.

6. **`_assets/` 안내만** — 로그 덤프·녹화 같은 대용량은 `~/projects/_assets/<project>/{deploy,data,refs}`. 만들지는 말고 필요해질 때. secret을 품으면 `chmod 700`.

7. **백업 확인** — 개인 머신이면 meta-repo가 붙어 있는지(`ls -d ~/projects/.git`) + cron 등록됐는지 **둘 다**. 🔑 **회사 머신은 붙이지 않는다** — 안 도는 게 정상이다.

8. **fork repo면 remote 점검** — `origin`=내 fork / `upstream`=원본 / `--push upstream DISABLED`. 누락이면 안내만(자동 변경 X).

**과설계 금지** — 자리만 만들고 내용은 작업하며 채운다.
