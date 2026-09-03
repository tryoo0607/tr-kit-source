# 영역: personal

사용자가 개인 소유로 명시한 자산과 프로젝트에 적용한다.

## 정책

- secret은 source에 평문으로 기록하지 않는다.
- local-docs는 프로젝트 source와 분리된 기록 저장소에 둔다.
- 외부 전송·push·배포는 대상과 영향을 보여주고 실행 전 확인한다.

개인 영역은 자동 기본값이 아니다. 명시적 project/env/profile 신호가 없으면 `unknown`으로 남는다.
