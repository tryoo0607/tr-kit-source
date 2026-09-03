---
name: secrets
description: secret(자격증명·키·토큰)을 관리하거나 코드/커밋에 들어갔는지 검사할 때 발동 — "secret 어떻게 관리해", "이거 커밋해도 되나", "secret 검사해줘", "git-crypt 셋업", pre-commit 훅. **탐지와 처리는 한 몸이다.**
---

# secrets

**찾고(scan) 처리한다(manage).** 둘은 한 몸이다 — 찾아도 어떻게 할지 모르면 소용이 없고, 처리 방법만 알아도 못 찾으면 새어나간다.

## 원칙 1 — 분리(externalize)가 먼저

config에 secret을 박지 말고 **빼서 참조**한다.

```
application.yaml   →  ${DB_PASSWORD}        평문 유지 (diff·리뷰 가능)
secrets.env        →  실제값                 이것만 암호화
```

소스에 하드코딩된 것은 외부화한다.

## 원칙 2 — 못 빼면 암호화 (git-crypt)

분리 불가한 secret 파일만 **git-crypt로 in-place 암호화**한다(작업트리 평문, repo 암호문). 별도 secret repo를 만들지 않는다.

| | |
|---|---|
| 키 방식 | **머신별 GPG** — 개인키는 그 머신에만, 이동 X, 개별 revoke 가능 |
| 복구 | **최소 2대 등록 + 복구용 키 1개 오프라인 백업**(passphrase 필수) |

셋업·복구·재암호화 = `references/git-crypt.md`

### 암호화 대상 (`.gitattributes`) — fail-closed

```
secrets.*  filter=git-crypt diff=git-crypt
*.key      filter=git-crypt diff=git-crypt
*.pem      filter=git-crypt diff=git-crypt
.env       filter=git-crypt diff=git-crypt
```
코드 프로젝트는 + `application-secret.yaml` · `*-secret.yaml` · `application-local.yaml`.

## 검사 — 툴 감지가 먼저

1. `gitleaks` · `trufflehog` · `detect-secrets` · `git-secrets` 설치 확인
2. **있으면** 그걸로 (정확도가 높다)
3. **없으면** 🔑 **패턴 fallback으로 조용히 가지 않는다** — 툴을 권하고 **설치할지 묻는다**(시스템 설치는 유저가 직접). 거절·급하면 패턴 fallback으로 가되 **약하다는 걸 알린다**

탐지 대상 · 패턴 · 훅 셋업 = `references/scanning.md`

## 🔑 발견했을 때 — 제거가 유일한 답이 아니다

**먼저 커밋을 막고**(blocker), 그 다음 상황을 가른다:

| 상황 | 조치 |
|---|---|
| 잘못 박힌 것 (코드·로그) | **제거 + 외부화** |
| 설정에 꼭 필요한 것 | **분리 우선** → 못 빼면 **git-crypt 대상 전환** |
| `.gitattributes` 미커버 | **패턴 등록** (아래 루프) |

> ⚠️ **이미 커밋·푸시됐으면 키를 로테이션한다(재발급·폐기).** 제거만으로는 부족하다 — 히스토리·원격·백업에 남는다. 히스토리 정리(`git filter-repo`·BFG)는 협업자 조율 후.

## 자기개선 루프

미커버 파일에서 secret이 나오면:

1. **외부화**(권장) 또는 **패턴 등록**
2. 등록하면 그 repo `.gitattributes`에 즉시 추가 (+ 재암호화)
3. 🔑 **범용 패턴이면 `/capture` 로 INBOX에 캡처** → 위 기본 패턴 목록 갱신 → **다음 repo부터 자동**

## 경계

| 일 | 어디 |
|---|---|
| 외부화 구현 | 「수행」 |
| 커밋 흐름 | `git` (커밋 전 이 스킬을 소환) |
| 리뷰 blocker 연계 | `review` |
| kit 내부 검사 | `setup/tools/validate` (kit 전용 — 이 스킬은 **임의 repo 대상**) |

**등록 머신·GPG 지문**(공개 정보)은 해당 repo의 보안 문서에 남긴다. **개인키는 절대 기록하지 않는다.**
