# 영역: unknown

project marker, environment, runtime profile에서 영역을 확정할 근거가 없는 상태다.

- 읽기·로컬 분석처럼 경계와 무관한 작업은 진행할 수 있다.
- 외부 전송·push·배포·공유처럼 소유 경계에 따라 허용 여부가 달라지는 작업은 대상 자산의 소유자를 먼저 확인한다.
- 영역을 반복해서 사용한다면 `profile-setup`으로 fallback을 설정하거나 project root에 `.tr-scope`를 둔다.
