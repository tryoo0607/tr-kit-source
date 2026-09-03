# secret 검사 (탐지·툴·훅·대응)

## 1. 툴 감지 → 권장 → 설치 여부
- 감지: `command -v gitleaks trufflehog detect-secrets git-secrets` 등.
- 없으면 **권장 제시**(하나 골라 설치할지 묻는다):
  | 툴 | 성격 |
  |---|---|
  | **gitleaks** | 빠르고 널리 씀, pre-commit·CI 쉬움 (기본 권장) |
  | trufflehog | 검증(verified) 시크릿 탐지 강함 |
  | detect-secrets | 베이스라인 관리(기존 오탐 억제) |
- 설치는 **유저가 직접**: `! brew install gitleaks` / `! go install ...` 등 안내(내가 시스템 설치 X).
- 거절/보류 → 아래 패턴 fallback.

## 2. 패턴 fallback (툴 없을 때)
탐지 정규식(대략):
- private key: `-----BEGIN [A-Z ]*PRIVATE KEY-----`
- AWS: `AKIA[0-9A-Z]{16}`
- 일반 토큰/키: `(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['"][^'"]{8,}`
- `.env`·자격증명 파일 staged 여부, high-entropy(base64/hex 긴 문자열).
- ⚠️ 패턴은 **오탐/누락** 있음 → 툴보다 약함을 알린다(그래서 툴 권장).

## 3. 발견 시 대응 (제거가 유일 답 아님)
1. **커밋 중단(blocker).**
2. **상황별 옵션 제시** (→ 이 스킬 연계):
   - **잘못 박힌 것**(코드·로그) → **제거 + 외부화**(환경변수·시크릿 매니저·`${ENV}` 참조).
   - **설정에 꼭 필요**(인프라 config·`application.yaml` 등) → **분리 우선**(secret 파일로 빼기) → 못 빼면 **git-crypt 암호화 대상 전환**.
3. **`.gitattributes` 미커버 파일이면 (자기개선 루프)**:
   - (a) 외부화, 또는 (b) **패턴 등록** → 그 repo `.gitattributes`에 즉시 추가(+ git-crypt 재암호화).
   - 범용 패턴이면 **`/capture` 로 INBOX에 캡처** → 이 스킬 기본 패턴 목록 갱신.
4. **이미 커밋/푸시됐으면**: **키 즉시 로테이션(재발급·폐기)** 최우선(제거만으론 유출 안 사라짐) + 히스토리 정리(`git filter-repo`/BFG, 협업자 조율).
5. `.gitignore`/`.gitattributes` 정비로 재발 방지.

## 4. 훅 셋업 (요청 시)
- `.pre-commit-config.yaml`에 gitleaks hook 추가(pre-commit 프레임워크) 또는 `.git/hooks/pre-commit`에 스캔 호출.
- repo에 이미 훅 체계 있으면 그 위에 얹음. CI에도 스캔 스텝 추가 권장.
