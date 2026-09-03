# 영역: work

조직이나 고객이 소유한 자산으로 사용자가 명시한 작업에 적용한다. 회사 고유 시스템·도구·절차는 public kit이 아니라 project-local 또는 조직 전용 plugin이 소유한다.

## 정책

- 조직 자산을 개인 저장소나 승인되지 않은 외부 서비스로 전송하지 않는다.
- 코드·설정·manifest·로그·증적의 소유 경계가 불명확하면 push·publish 전에 묻는다.
- secret은 source와 local-docs에 평문으로 기록하지 않는다.
- 조직 전용 양식과 실행 권한을 혼동하지 않는다. 커밋·MR·배포는 명시적 요청이 있을 때만 실행한다.

## 우선순위

project-local 규칙과 조직 전용 plugin을 먼저 적용하고, public kit은 공통 workflow만 제공한다. 정책과 guard는 어느 한쪽이 금지하면 실행하지 않는다.
