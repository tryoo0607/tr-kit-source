# 선택한 공식 설치본 검수

## 역할과 근거

- 공식 설치기의 설치·업데이트를 재구현하지 않는다. 기존 provider resolver의 entry pin 뒤에 설치 증거와 리소스 대조를 연결한다. 원문이나 runtime을 kit에 가져오지 않고 외부 파일의 경로·크기·hash만 기록한다.
- 설치 근거는 공식 manager의 선택된 설치 기록·manifest·lock/receipt와 해당 버전의 공식 설치 문서를 대조한다. 임의 `source` 문자열, package.json 하나, 로컬 검수 문서만으로 진짜 공식 배포물임을 인증할 수 없다. 원문 대조 checkout·구 kit 변형본은 실행 설치본이 아니다.
- 파일 목록의 범위는 명시한 설치 디렉토리다. entry가 읽는 reference·template·script·모듈 기록과 제품별 resource를 포함해야 한다. 설치 디렉토리 밖의 Node/Bun·Python·npm 의존·브라우저·프로젝트 `_bmad` 등이 필요하면 별도 공식 설치·검증 근거를 확인하고 미충족 항목은 `unresolved`에 남긴다. 경로의 존재를 실제 ABI·브라우저·MCP 동작으로 확대하지 않는다.

## 기록과 재검수

1. `<kit>/scripts/provider-review.py snapshot`에 기존 `--root --declaration --product --id --kind`와 `--installation <외부 설치 root> --method <공식 관리 종류> --source <공식 HTTPS URL> --evidence <설치 근거 파일>`을 전달한다. evidence는 여러 번 지정할 수 있다. stdout만 출력하고 설치·등록·실행·파일 저장을 하지 않는다. 저장은 승인된 로컬 기록 경로에서 수행한다.
2. 출력은 `pending` 초안이다. evidence의 내용·출처와 실제 선택 버전, 전체 필수 리소스·제품 지원·고유 정책 충돌을 검토한다. 확인한 제품만 `products.<제품>.status=supported`, `basis`에는 실제 근거 위치와 확인 범위를 적는다. 나머지는 unverified/unsupported로 유지한다. 미결이 모두 해소된 경우에만 `unresolved=[]`, `review_status=reviewed`로 기록한다. 이름이나 파일 수를 맞추려고 미결을 지우지 않는다.
3. 동일 선택 입력과 `verify --review <명시 기록>`으로 entry·전체 리소스·설치 근거의 현재 bytes를 대조한다. 성공은 `review-record-verified`이며 **로컬 검수 기록과 일치**한다는 뜻이다. 검수 작성자 인증·공급망 서명·모델 준수·native 실행 성공은 증명하지 않는다. 문서의 주장과 실제 설치·행동 검증을 따로 보고한다.
4. 업데이트에는 이전 기록을 보존하고 새 snapshot을 만든 뒤 `compare --before <이전> --after <새>`를 사용한다. 추가·삭제·변경 파일, 버전/설치 identity·증거·제품 계약 차이를 실제 이전/새 공식 지침과 함께 검토한다. 비교 성공은 승인이나 자동 repin이 아니다. 연결 의도·고유 요구 보존과 필요한 행동 시험을 대조한 뒤 새 기록을 채택한다.

## 실패와 한계

- 부재·제품 미검수·필수 리소스 미결·변경·비정상 입력은 exit2다. 외부 원문/예외를 그대로 출력하지 않는다. snapshot/compare exit0도 실행 준비 완료를 뜻하지 않는다.
- symlink·특수 파일은 따라가지 않고 보류한다. 현재 상한은 파일8192개·전체256MiB·개별64MB다. 큰 설치는 임의 누락으로 통과시키지 말고 공식 manager의 설치 단위와 필수 외부 의존을 분리해서 검토한다. 이 상한은 조회 승인량의 공통 기준이 아니다.
- hashes는 검사 시점의 변경 감지다. 관리자·검수 파일을 바꿀 수 있는 주체를 방어하거나 검사와 실행 사이의 변경을 OS 수준으로 막지는 않는다. 자연어 업무 wrapper에는 지침상 적용이며 범용 파일 접근 차단 hook은 아니다.
- 자체 Claude-Mem 실행기는 schema2 binding의 명시 `reviews` 두 개를 start/MCP 실행 전에 재검사한다. schema1은 plan/doctor·출력과 기존 소유 worker의 stop 검사를 유지하되 새 실행을 허용하지 않는다. 검수 실패가 기존 소유 worker의 안전한 중단을 막는 별도 금지가 되지 않게 한다.
