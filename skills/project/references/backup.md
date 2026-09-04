# 백업 — `_docs` Git 저장소

작업 기록은 프로젝트 repo 밖의 `~/projects/_docs/`에 모으고, 그 디렉터리를 포함하는 Git 저장소의 일반 commit·push 흐름으로 백업한다. 별도 host binary나 cron 설치를 요구하지 않는다.

## ⛔ 개인 머신에서만

회사 머신에는 개인 원격을 연결하거나 push하지 않는다. 회사 정책이 허용한 사내 원격이 따로 있을 때만 그 저장소 규칙을 따른다.

## 확인

```sh
git -C ~/projects rev-parse --show-toplevel
git -C ~/projects status --short -- _docs
git -C ~/projects remote -v
```

- `_docs` 변경이 status에 보여야 한다.
- 프로젝트 코드 repo는 각각 독립 저장소이므로 local-docs commit에 포함하지 않는다.
- 원격 push는 외부 전송이므로 변경 범위와 대상 remote를 먼저 확인하고 승인 후 실행한다.

## 백업

1. `git -C ~/projects status --short -- _docs`로 기록 변경만 확인한다.
2. `_docs`만 stage하고 한 줄 Conventional Commit으로 기록한다.
3. staged diff와 remote를 확인한다.
4. 승인 후 일반 push하고 upstream과 동기화됐는지 확인한다.

성공 기준은 “commit이 생김”이 아니라 의도한 `_docs` 변경이 남지 않고 승인된 remote에 반영된 상태다.

## 대상이 아닌 것

- `_assets/` — 대용량 원본
- 각 프로젝트 repo의 코드 — 각자 자기 원격이 소유
- 회사 기록의 개인 GitHub 전송
