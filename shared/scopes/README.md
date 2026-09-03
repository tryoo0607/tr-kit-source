# 영역(scope)

영역은 **지금 다루는 자산이 어느 경계에 속하는가**를 나타낸다. profile이 기능과 저장소 연결을 나타내는 것과 별개다.

## 판정

`hooks/lib.sh`는 다음 순서로 `personal`, `work`, `unknown`을 판정한다.

1. git root의 local `.tr-scope` 파일
2. `TR_KIT_SCOPE` 환경변수
3. runtime profile의 `public.scope.default`
4. 어느 것도 없으면 `unknown`

특정 회사명·머신명·계정명·GitHub owner를 추론 규칙으로 사용하지 않는다. `.tr-scope`를 둘 경우 repository에 커밋할지는 해당 프로젝트 정책으로 결정한다.

정책이 겹치면 금지는 합집합으로 적용한다. `unknown`인데 영역에 따라 허용 여부가 달라지는 외부 전송·배포·저장 작업은 먼저 사용자에게 확인한다.
