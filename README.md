# tr-kit-source

Codex·Claude에서 개발·조사·자료 활용·세션 인계를 돕는 공통 플러그인 소스다. 외부 skill·도구를 고정 commit으로 재사용하고 제품별 조립과 역할을 관리한다.
공통 배포물은 `tr-codex`, `tr-claude`이며 개인 인프라·백업·REA 환경은 별도 `tr-kit-private` 소유다. 공통 설치에 개인 기능·자료 전송이 따라오지 않는다.

## 준비와 시작

아래 명령은 소스 저장소 루트 기준이다. CI와 같은 Python 3.12, Git과 외부 source 취득용 네트워크를 준비한다. 스킬 검수·테스트에는 PyYAML이 필요하며 CI는 6.0.3을 사용한다.

```bash
python3 -m pip install 'PyYAML==6.0.3'
python3 scripts/fetch_sources.py
./build.sh codex --plugin-hooks --output out/codex
```

출력은 존재하지 않는 새 경로를 사용한다. fetch는 `.cache/upstreams`에 선언한 commit을 취득하고 기존 checkout을 reset하지 않는다. build는 자동 다운로드하지 않는다.
기존 cache를 지정하면 fetch의 `--cache`와 build의 `TR_KIT_SOURCE_CACHE`를 맞춘다.

```bash
./install.sh codex out/codex
```

기본값은 생성물 무결성을 검사하고 native 설치 명령을 보여주는 dry-run이다. Codex CLI가 있는 환경에서 검토 후 적용하려면:

```bash
./install.sh codex out/codex --apply
```

이는 marketplace 등록과 `tr-codex@tr-codex` 설치를 호출한다. 기존 설치·전역 지침·실행 중 캐시 보존 및 복구는 [ROLLOUT.md](ROLLOUT.md)를 따른다.
설치 → 제품 hook trust → 실제 저장소의 Git hook 등록 → 세션 반영은 별도 확인이다. `--plugin-hooks`는 공통 PreToolUse hook을 포함할 뿐 trust나 저장소 등록을 수행하지 않으며 새 지침은 기존 세션에 자동 소급되지 않는다.
저장소 등록·기존 hook 보존·복구는 [Gitleaks 안내](common/base/skills/security-scan/references/gitleaks.md), 선택 도구 설치와 runtime 전제는 [빌드 계약](BUILD-CONTRACT.md)을 확인한다. BMAD의 uv, Claude-Mem의 Bun·worker 등도 별도 필요하다.

Claude 조립은 다음과 같이 지원하지만 현재 `install.sh`는 Codex만 받는다. 운영 전환은 Codex pilot 우선이며 Claude native 검증은 별도다.

```bash
./build.sh claude --plugin-hooks --output out/claude
```

Wiki 진입점은 Codex `wiki`, Claude `wiki-manager`이며 `wiki-query`는 각각 해당 진입점에 의존한다.

## 맡길 수 있는 작업

| 목적 | 담당 |
|---|---|
| 요구·조사·설계·구현·검증 | BMAD |
| 기술 문서/API, 화면 제작·브라우저 검증 | find-docs / Context7, frontend-design / Playwright |
| 구조·관계·처리 흐름 시각화 | Archify 기본; 명시한 도구·형식 우선 |
| 수치 차트·일정·칸반·사용자 여정 | diagram-design |
| 코드·의존성·이미지·IaC 및 커밋·전송 검사 | security-scan / Semgrep / Trivy / Gitleaks / Git guard |
| 원본 보관·검색, 기록·경험·지식 연결 | document / Claude-Mem / LLM Wiki |
| 저장소·worktree 배치, 세션 재개·인계 | project / Worktrunk, session / Orca CLI |
| README 작성·갱신·감사 | github-readme-generator |
| 로컬 연결·skill 저작 | profile-setup / skill-authoring / skill-creator |

각 업무 skill이 분석·산출물·검증을 맡고 document는 보관·검색과 기록 연결을 맡는다. 요청 전달·수신 확인·실제 완료는 구분하며 전달로 수신 호스트 권한이 확대되지 않는다.

## 구조와 운영 자료

`common/base/`는 공통 지침·skill, `adapters/codex/`와 `adapters/claude/`는 제품별 보정·MCP·hook을 담는다. `sources.toml`과 각 `dependencies.toml`이 외부 출처와 commit을 고정한다.
`.cache/upstreams/`와 `out/`은 정본이 아니며 생성물인 `out/`을 직접 수정·커밋하지 않는다. 생성된 `assembly.json`은 파일·출처·hash, `release.json`은 배포 무결성과 source revision 확인에 쓴다.
source와 생성물 배포 저장소는 구분한다. 양 제품 게시는 원자적이지 않으며 한쪽만 게시되면 원인을 해결한 뒤 같은 source commit으로 재실행한다.
[구조](ARCHITECTURE.md) · [빌드 계약](BUILD-CONTRACT.md) · [기여](CONTRIBUTING.md) · [적용·복구](ROLLOUT.md) · [감사·미결](AUDIT.md) · [보안](SECURITY.md)

## 배포 검증

두 제품을 같은 source commit으로 `out/codex`, `out/claude`에 조립한 뒤 실행한다. `SOURCE_COMMIT_SHA`는 실제 전체 40자리 SHA로 대체하고 clone 경로는 존재하지 않는 새 경로를 사용한다.

```bash
python3 scripts/delivery.py --built-root out --clone-root /tmp/tr-kit-delivery-check --source-revision SOURCE_COMMIT_SHA
```

기본 검증도 네트워크 clone과 임시 clone의 파일 교체·staging을 수행하지만 commit·push는 하지 않는다. 실제 게시에는 `--push`, `TR_KIT_ALLOW_PUSH=1`, clean source와 배포 권한이 필요하다. [CI](.github/workflows/build.yml)와 [delivery 구현](scripts/delivery.py)이 정본이며, 게시는 호스트 설치·활성화와 별개다.

## 데이터 경계와 검증 한계

기존 문서·원본·프로젝트를 자동 이관하지 않는다. 경로·공유 범위는 호스트 설정 소유이며 회사 자료를 개인 NAS·Wiki·백업에 자동 반입하지 않는다. private 설치도 자료 반입·timer·원격 변경의 일괄 승인이 아니다.
Git guard는 등록된 저장소의 index와 outgoing commit을 검사한다. 로컬 전용 경로는 명시 등록하며 `runs/` 이름만으로 전역 금지하지 않는다. 로컬 hook은 우회 가능하므로 공유 범위 검토를 대신하지 않는다.
조립·형식·도구 검증만으로 모델의 skill 자동 선택, UI 품질, 운영 자료 연결·새 세션 반영 성공을 판단하지 않는다. Context7 실조회는 `--network-context7`이 필요하며 worker 부재를 검색·저장 성공으로 보고하지 않는다.
통합 `kit-audit`와 PTBMAF·Design Doc 전용 skill은 구현·도입 완료로 취급하지 않는다. Obsidian은 보류 상태이며 필수 의존성이 아니다.
공통 자체 소스는 [LICENSE](LICENSE), 외부 skill·runtime은 각 upstream 라이선스와 고지를 따른다.
