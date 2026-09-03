# git-crypt (머신별 GPG) 셋업·운용·복구

작업트리는 평문, repo는 암호문. 지정 파일만 자동 암/복호(clean/smudge 필터).

## 0. 설치 (감지 우선)
- `command -v git-crypt` 확인 → 없으면 안내(유저 실행): `sudo apt install -y git-crypt` / `brew install git-crypt`. gpg도 필요.

## 1. 키 방식 = 머신별 GPG
각 머신이 자기 GPG 키로 unlock. 개인키는 그 머신에만(이동 X). 개별 revoke 가능.

### repo 최초 셋업 (한 번)
```bash
cd <repo>
git-crypt init                       # 내부 AES 키 생성
# .gitattributes 작성(아래 패턴) 후
git-crypt add-gpg-user <내-GPG-지문>  # 이 키로 repo키 잠금 → repo에 커밋됨
```
### 머신 추가
```bash
# 새 머신에 GPG 키가 있으면(없으면 gpg --full-generate-key, passphrase 필수)
git-crypt add-gpg-user <새머신-GPG-지문>   # 재암호화 커밋 (기존 등록 머신에서 실행)
# 새 머신에서 pull 후 자동 복호(그 머신 개인키로)
```
### 머신 제거(revoke)
- `.git-crypt/keys/…/<지문>.gpg` 제거 + **git-crypt로 새 키 재발급·재암호화**(제거만으론 과거 접근 유효). 유출 머신은 반드시 재암호화.

## 2. 복구 전략 (재난)
git-crypt는 **모든 등록 키로** repo키를 암호화 → 등록 머신 아무거나로 복호 가능.
- **한 머신 죽음** → 다른 등록 머신에서 정상. (죽은 키는 나중에 revoke)
- **전부 죽음** 대비 → **복구용 GPG 키 1개를 오프라인 백업**:
  - 위치: 비번관리자(암호볼트)/클라우드/암호화 USB. **개인키엔 passphrase 필수**(파일 새도 못 씀).
  - passphrase는 키 파일과 **다른 곳**에.
  - ⚠️ NAS 등 홈랩 내부는 비추(같이 날아갈 수 있음).
- 최소 **2대 이상 등록** + 복구키 1개 = 단일 장애 커버.

## 3. 암호화 대상 (`.gitattributes`) — fail-closed
```
secrets.*  filter=git-crypt diff=git-crypt
*.key      filter=git-crypt diff=git-crypt
*.pem      filter=git-crypt diff=git-crypt
.env       filter=git-crypt diff=git-crypt
# 코드 프로젝트: application-secret.yaml, *-secret.yaml, application-local.yaml 등 추가
```
- secret은 **분리 우선**(→ SKILL 원칙1). 못 빼는 것만 위 패턴 파일에.
- ⚠️ 암호화 설정 **전에 평문 커밋된 secret은 히스토리에 남음** → 처음부터 대상으로, 이미 노출됐으면 **로테이션**.

## 4. 미커버 패턴 루프
이 스킬의 검사이 미커버 파일에서 secret 발견 → 외부화 or 패턴 등록. 등록 시 `.gitattributes` 추가(+재암호화), 범용이면 `/capture` → 기본 패턴 승격.

## 5. 등록 대장 기록 (지문만)
- 등록된 머신·GPG **지문**(공개 정보)은 해당 repo의 보안 문서에 표로 남긴다. **개인키는 절대 기록 X.**
- 상태: `git-crypt status` (암호화 대상·현황 확인).
