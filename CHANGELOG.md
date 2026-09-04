# Changelog

이 프로젝트의 공개 release 변경을 기록한다. 개인 작업 일지와 운영 환경 이력은 포함하지 않는다.

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
