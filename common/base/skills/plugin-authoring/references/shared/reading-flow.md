# 읽기·호출 흐름 검사

## 목적과 역할 경계

- 적용 여부는 진입점 SKILL.md의 '조건부 공통 절차'에서 정한다. 이 파일은 선택된 흐름의 검사 방법을 소유하며 발동 조건을 별도로 변경하지 않는다.

## 수행 방법과 절차

- 대표 요청에서 실제로 읽는 자료와 호출 대상을 순서대로 따라간다.
  - 최초 본문과 공통 필수 제약
  - 분기 선택 조건과 조건부 reference
  - 연결 대상과 전달 입력·필요한 결과
- 지침 읽기, 실제 도구 실행, 독립 세션 호출을 구분한다.
- 흐름에 표시한 참조 대상과 실행 주체를 실제 파일·설정·관측과 대조한다. 단순 reference 읽기를 독립 실행·자동 결과 반환으로 판정하지 않는다.
- 다음 문제를 확인한다.
  - 필수 자료·제약 누락
  - 끊긴 참조와 호출 연결
  - 반복 읽기와 중복 수행
  - 담당이 없는 단계
  - 파일 포함 관계와 참조·실행·보고 관계를 섞어 잘못 표현한 연결
- 읽기량은 파일별 길이뿐 아니라 대표 요청에서 함께 읽는 범위와 중복을 전후 비교한다.
  - 외부 지침·템플릿·작업 데이터·환경 주입 등 측정에 포함한 범위를 밝힌다.
  - 매번 읽는 내용을 reference로 옮긴 것만으로 절감이라고 보고하지 않는다.
  - 문자 수를 토큰 수나 비용 절감률로 바꾸어 보고하지 않는다.
- 정적 경로 대조와 실제 모델이 읽고 수행한 관측을 구분한다.
- 코드나 문서상 링크의 존재만으로 실제 전달·수행 성공을 보고하지 않는다.

### 선언한 읽기량의 자동 측정

- 전후 기준본과 동일 요청의 읽기 목록이 있으면 kit 루트의 `scripts/context_check.py`를 사용한다. 공통 로직은 `common/base/scripts/context_check.py`에 있다. Python/PyYAML이 필요하며 부재 시 설치를 자동 수행하지 않고 측정 미실행으로 보고한다.
- 일반적인 수치 대조는 다음처럼 **측정 모드**로 실행한다. 원래 파일이나 설정을 변경하지 않고 JSON을 stdout으로 출력한다. 결과를 별도 파일에 저장할 때는 승인된 로컬 기록 위치를 사용한다.

  ```text
  python3 -B scripts/context_check.py --before /absolute/baseline --after /absolute/candidate --cases /absolute/cases.json --measure-only
  ```

- cases는 기존 JSON 배열 또는 `schema_version: 1`, `cases`와 선택 `discovery`를 갖는 객체다. 각 case의 `name`, `before`, `after`를 선언한다. 읽기 항목은 root 상대 `path`와 선택한 `section` 제목이다. `SKILL.md`는 전체만 허용하며 reference의 절은 제목·하위 절을 포함해 다음 동급/상위 제목 전까지 센다. 대상 밖 경로·파일/제목 부재·중복 제목은 측정 오류다. 누락 항목을 자동으로 제외하거나 0으로 처리하지 않는다.
- 발견 metadata는 기본적으로 `common/base/skills` 또는 기존 flat `skills` 중 하나의 name/description을 별도로 센다. 둘 다 있으면 cases의 `discovery.before/after` 또는 `--before-skills/--after-skills`로 scope를 명시한다. 디렉토리/entry 부재는 오류이며 “발견 비용0”으로 성공 처리하지 않는다. 네이티브 제품이 실제 발견/주입한 목록이나 전체 외부 provider 목록의 실측으로 확대하지 않는다.
- 문자 수는 UTF-8을 해석한 Unicode code point 수다. 파일의 CRLF를 보존하며 metadata는 YAML이 해석한 name/description 값을 센다. 정확히 같은 구간의 재독뿐 아니라 같은 canonical 파일의 전체/절 겹침도 중복으로 센다. 다른 파일의 유사 문구·의미 중복을 추정하지 않는다. 각 read의 source hash를 남기며 측정 중 파일/경로 변경은 오류다.
- 절 선택은 ATX `#` 제목과 backtick/tilde fenced code 구분을 지원하는 source 측정용 부분 parser다. Markdown 전체 renderer가 아니며 Setext 제목·복합 container/HTML block의 렌더 의미까지 검증하지 않는다. 그런 형식이면 전체 파일을 선언하거나 별도로 확인하고 unsupported 범위를 남긴다.
- `unmeasured`는 양쪽 공통 미측정, `unmeasured_before/after`는 한쪽 미측정을 적는다. 외부 공식 지침·실제 CLI guide/반환·작업 데이터·환경 주입을 포함했는지 명시한다. 예제 `scripts/context-cases.json`은 새 source의 부분 경로5개이며 모든 요청/필수 지침을 자동 포괄하는 정본이 아니다. 조건이나 경로가 달라지면 실제 읽기 목록을 확인해 별도 선언한다. 외부 자료를 측정하려고 kit에 복사하지 않는다.
- 기존 비증가 비교 기능도 유지한다. `--measure-only`를 생략하면 case별 chars와 중복이 기준보다 늘지 않는지, 발견 metadata 합계가 늘지 않는지 검사한다. case의 `allowed_growth_chars`는 비음수 정수이며 양수이면 `growth_reason`이 필요하다. tool 입력의 허용값/이유를 적었다는 사실 자체는 사용자 합의나 승인 증거가 아니다. 승인된 비교 기준이 필요할 때만 이 판정을 사용하며 모든 저작에 비증가를 새 의무로 부과하지 않는다. 중요한 요구·금지·실패 대응을 줄여 통과시키지 않는다.
- exit 0은 측정 성공(측정 모드) 또는 해당 선언 범위의 비교 통과, exit 1은 측정했지만 비증가 비교 미통과, exit 2는 입력·대상·dependency·측정 오류다. 단순 실패 코드만으로 요구 위반/누락이나 source 작업 미완료로 결론내리지 않는다. 측정된 부분의 결과를 전체 모델 읽기·token·비용·의미 보존·발동 성공으로 확대하지 않는다.

## 결과와 완료 판단

- 결과에는 요청·선택 경로·확인한 자료·발견 사항·미확인·측정 범위를 남긴다.
