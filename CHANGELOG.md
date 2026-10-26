# Changelog

이 프로젝트의 공개 release 변경을 기록한다. 개인 작업 일지와 운영 환경 이력은 포함하지 않는다.

## 0.6.0 — Unreleased

- common/base와 제품별 adapters 중심으로 소스를 개편하고 이전 core/shared/recipe 및 lifecycle hook 구현을 제거한다.
- BMAD, Claude-Mem, LLM Wiki와 개발 지원 skill을 정확한 upstream commit 및 제품별 binding으로 조립한다.
- 기존 tr-codex와 tr-claude marketplace 이름을 유지하고 양 제품의 빌드·검수·배포 dry-run 및 main 자동 배포를 연결한다.
- 생성물에 source revision과 파일 hash를 기록하고 로컬 캐시가 배포물에 섞이지 않도록 한다.
- 문서·프로젝트 및 로컬 호스트 전환 기준을 정리한다. 원격 배포와 실제 호스트 적용 완료를 뜻하지 않는다.

## 0.5.6 — 2026-09-07

- 재부팅 시 Happy daemon 자동 시작과 session snapshot·안전 cycle을 위한 임시 host 호환 계층을 추가한다.
- 양 target이 공유하는 hook 동작을 동일 fixture runner로 검증한다.
- LLM Wiki 작업 메타가 본문 표에 오염되는 문제를 수정하고 단계·자리표시 값 검증을 보강한다.

## 0.5.5 — 2026-09-04

- Happy가 제공하는 reconnect session ID를 우선 사용해 Codex `/clear` 후 state 인계를 복원한다.
- `/dev/null`·fd 간 redirection을 파일 변경으로 오인하던 Stop 훅 판정을 수정한다.
- 더 이상 배치하지 않는 legacy host binary 의존과 설치 안내를 제거하고 local-docs 백업을 일반 Git 흐름으로 맞춘다.
- Happy Agent SDK 설정은 PolyGarden 전환 전까지만 유지하는 임시 호환 경로로 명시한다.

## 0.5.4 — 2026-09-04

- Codex 컨텍스트 60%에서 인계 state를 준비하고 75%에서 `/clear` 가능 시점을 안내한다.
- Happy session identity를 기준으로 `/clear` 후속 세션에 최신 state를 한 번 주입한다.
- 실행 중 Happy/Codex 세션을 inventory하고 canary 방식으로 안전하게 갱신하는 도구를 추가했다.

## 0.5.3 — 2026-09-04

- split 이후 source worktree를 정확히 식별하는 `kit-verify`와 빠른 hook 검증을 추가했다.
- 로컬·CI·delivery의 전체 검증을 `tools/validate.py full` 단일 진입점으로 통합했다.

## 0.5.2 — 2026-09-04

- knowledge와 project가 공유하는 LLM Wiki core와 local-docs v2 migration을 추가했다.
- README 구조 도표와 skill description의 발동 경계를 정리했다.
- `kit`의 skill authoring 계약에 routing, progressive disclosure, port attribution, 검증 기준을 보강했다.

## 0.5.1 — 2026-09-03

- 공개 구조와 target 산출 흐름을 README에서 표와 단일 축 도표로 명확히 설명했다.
- GitHub Actions의 checkout과 Python setup action을 최신 major로 갱신했다.

## 0.5.0 — 2026-09-03

- 공통 core, target adapter, recipe 기반 정적 합성 구조를 도입했다.
- 개인 workflow를 external private pack 경계로 분리했다.
- runtime profile과 contract-driven binding을 추가했다.
- 두 target 배포 저장소를 source가 전부 생성하는 managed-root mirror로 전환했다.
