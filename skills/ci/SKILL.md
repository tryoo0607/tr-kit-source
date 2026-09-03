---
name: ci
description: CI/CD 파이프라인(**GitHub Actions**)을 작성·수정할 때 발동 — "CI 짜줘/워크플로 만들어줘/파이프라인 추가/actions 설정", "빌드·테스트 자동화 YAML". 스테이지(lint→test→build→deploy)·트리거·캐싱·secret 관례로 `.github/workflows/*.yml` 산출. 실패 디버그는 `odin:gh-fix-ci` 소프트의존. GitLab 등은 범위 밖(GHA 전용 — 회사는 project-local 우선).
---

# ci (GitHub Actions 파이프라인 작성)

CI/CD 워크플로를 **GitHub Actions**로 작성·수정한다. `.github/workflows/*.yml` 산출. **작성**이 목적 — 실패한 CI **고치기**는 `odin:gh-fix-ci`에 위임. 정본 양식·스니펫 = `references/github-actions.md`.

## 관례 (기본값, 조정 가능)
| 축 | 기본 |
|---|---|
| **스테이지** | lint → test → build → (deploy, 선택) |
| **트리거** | `push`(기본 브랜치) + `pull_request`. 배포/릴리스는 `tag`(`v*`) |
| **캐싱** | 언어별 캐시(Go modules·npm·pip). `actions/setup-*`의 cache 옵션 우선 |
| **secret** | **GitHub Actions secrets**(repo/org). 워크플로에 평문 금지. (repo 파일 secret=git-crypt는 별개 층) |
| **매트릭스** | 필요 시 OS·버전 매트릭스. 과하면 지양 |

- **비처방** — 프로젝트 언어·필요에 맞춰 스테이지 넣고 뺌. 작은 repo는 test만.

## 절차
1. **대상 파악** — 언어·빌드도구·테스트 명령·배포 유무 확인(알아내기 profile로 현행 파악 가능).
2. **스테이지 구성** — 위 관례로 job 설계. 무엇을 lint/test/build 하는지는 **`test`·프로젝트 규약**과 정합.
3. **양식 적용** — `references/github-actions.md` 스니펫으로 `.github/workflows/<name>.yml` 작성.
4. **secret·권한** — 필요한 secret은 **이름만** 워크플로에(`${{ secrets.X }}`), 실제값은 GH Actions secrets에 유저가 등록(report-first 안내). `permissions:` 최소권한.
5. **검증** — YAML 문법·액션 버전 확인. 실제 실행 실패는 `odin:gh-fix-ci`.

## 소프트의존/위임
- **실패 CI 디버그·수정** = **`odin:gh-fix-ci`** 있으면 우선(실패 로그→수정), 없으면 로그 직접 읽어 진단. (INTEGRATIONS: odin=소프트의존)
- **로컬 커밋훅**(lint/format을 커밋 시점에) = **`odin:setup-pre-commit`** — CI와 상보(로컬 게이트 + CI 게이트).
- 뭘 테스트/빌드하는지 = `test`·`convention`와 정합. secret 관리 = `secrets`.

## 경계
- 여기 = **GitHub Actions 작성**. 회사(GitLab CI 등)는 **project-local·`tr-work` 우선**(사내 양식). self-hosted 러너·홈랩 CI는 필요 시 확장(지금 범위 밖).
- 배포 대상 인프라 설정은 해당 도메인 plugin이 담당한다. 여긴 파이프라인만.
