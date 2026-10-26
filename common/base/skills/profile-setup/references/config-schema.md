# 설정 규격

설정 작성, 검증 또는 소비자의 경로와 정책 해석이 필요할 때 읽는다. 확인된 해석 결과는 재사용한다. 새 설계의 TOML 규격 초안이며 실행 parser, validator와 동기화 도구의 지원을 뜻하지 않는다.

## 입력과 전제

호스트별 설정 파일은 `$XDG_CONFIG_HOME/tr-kit/config.toml`이다. 변수가 없거나 비어 있으면 `~/.config/tr-kit/config.toml`을 사용한다. 다른 파일을 명시적으로 선택했다면 그 파일 하나를 사용하며 여러 파일을 자동 병합하지 않는다. 기존 profile.d 파일을 읽거나 이관하지 않는다.

이 설정은 로컬 경로와 정책을 담는다. 호스트마다 실제 값을 확인하며 문서 동기화 대상에 설정 파일을 자동 포함하지 않는다. project/group 식별자는 기존 등록에서 재사용하고 소속 명부는 저장하지 않는다.

## 수행 방법과 절차

### 설정 해석 순서

1. 명시적으로 선택된 설정 파일 또는 기본 위치의 파일 하나를 사용하고 schema_version을 확인한다. 파일 간 병합과 기존 profile.d의 자동 상속은 하지 않는다.
2. 필요한 필드의 자료형과 허용 값을 확인하고 누락된 선택 값에는 아래 기본값을 적용한다. 미지원 필드/버전은 해석을 보류한다.
3. 소속별 명시 경로를 우선하고 생략된 경우에만 roots의 기본 배치를 계산한다. roots.code는 repo 경로 자동 계산에 사용하지 않는다. 명시 경로의 출처와 계산된 값의 근거를 구별한다.
4. 소속별 동기화 table은 기본 정책 전체를 대체한다. 개인 knowledge는 별도 정책을 사용한다. 이 해석은 전송을 실행하지 않는다.
5. 실제 경로/등록과 경계 충돌, 소비자 지원을 확인한다. 충돌하면 현재 자료를 보존하고 영향을 받는 적용을 보류한다.

### 필드와 기본값

표에 없는 필드, 다른 자료형과 지원하지 않는 버전은 오류로 알린다. 선택 table은 생략할 수 있으며 TOML에는 null을 쓰지 않는다. `string[]`은 중복 없는 문자열 배열이다.

| 필드 | 자료형 | 필수와 기본값 | 의미와 제약 |
|---|---|---|---|
| `schema_version` | integer | 필수, `1` | 이 초안의 버전. 기존 profile 계약과 별개 |
| `roots.code` | string | 선택, 기본값 없음 | 코드 공간의 기준 위치. repo 경로를 이름으로 자동 조합하지 않음 |
| `roots.documents` | string | 선택, 기본값 없음 | 소속별 문서 위치를 계산할 기준 |
| `roots.assets` | string | 선택, 기본값 없음 | 문서와 분리한 대용량 자료 기준 위치 |
| `projects.<id>.code` | string | 선택, 기본값 없음 | 해당 project의 기본 checkout 연결. 실제 등록과 다르면 충돌 확인 |
| `projects.<id>.documents`, `projects.<id>.assets` | string | 선택 | 해당 소속의 전체 경로 override |
| `groups.<id>.documents`, `groups.<id>.assets` | string | 선택 | group 공통 자료의 전체 경로 override |
| `common.documents`, `common.assets` | string | 선택 | project/group 밖 공통 자료의 전체 경로 override |
| `knowledge.documents`, `knowledge.assets` | string | 선택, 기본값 없음 | 개인 지식 문서와 대용량 자료의 독립 경로. 기존 private repository도 명시적으로 연결 |
| `documents.sync` | table | 선택, 동기화 꺼짐 | project/group/common 문서에 적용할 기본 동기화 정책 |
| `projects.<id>.sync`, `groups.<id>.sync`, `common.sync` | table | 선택 | 해당 소속 문서의 동기화 정책 전체를 대체 |
| `knowledge.sync` | table | 선택, 동기화 꺼짐 | 개인 지식 문서의 독립 동기화 정책. `documents.sync`와 `common.sync`를 상속하지 않음 |
| `sync_targets.<id>.repository` | string | 대상 정의 시 필수 | 확인할 로컬 Git 저장소 루트 |
| `sync_targets.<id>.remote` | string | 대상 정의 시 필수 | 그 저장소에 이미 등록된 remote 이름. URL이나 인증값을 넣지 않음 |

동기화 정책 table은 아래 필드만 사용한다.

| 필드 | 자료형 | 기본값 | 의미와 제약 |
|---|---|---|---|
| `enabled` | boolean | `false` | 동기화 허용 여부. 실행 지시는 아님 |
| `targets` | string[] | `[]` | 허용한 `sync_targets` 식별자. 켜짐이면 하나 이상 필수 |
| `exclude` | string[] | `[]` | 해당 소속 문서 경로 안에서 전송을 제외할 상대경로 |

### 경로와 식별자 해석

- 경로는 비어 있지 않은 절대경로 또는 `~/`로 시작하는 경로다. `~`는 현재 호스트 사용자 홈으로만 해석하며 환경변수, shell 명령과 glob을 확장하지 않는다. 경로 필드의 `..` 구성요소는 허용하지 않는다.
- `<id>`는 `[A-Za-z0-9][A-Za-z0-9._-]*` 형식이다. 등록 식별자가 이 형식에 맞지 않으면 임의로 치환하지 않고 식별자 연결 설계를 먼저 해결한다. config 항목의 존재가 project/group 신규 등록이나 소속 변경을 뜻하지 않는다.
- project/group/common의 문서와 assets 위치는 소속별 override가 우선이다. 없으면 각각의 root 아래 `projects/<id>`, `groups/<id>`, `common`을 사용한다. 해당 root도 없으면 그 위치가 필요한 작업만 보류한다. group 설정은 소속 project에 상속하지 않는다.
- 개인 지식은 `knowledge.documents`와 `knowledge.assets`의 명시 경로만 사용한다. roots나 common으로 대체하지 않으며 누락된 위치가 필요한 작업만 보류한다. 문서 루트 아래 별도 knowledge 경로를 명시하거나 기존 private repository를 연결할 수 있다. 소속 간 경로 충돌 검사는 동일하게 적용한다.
- 기존 문서 정본과 작업 공간은 확인된 현재 경로를 사용한다. 설정과 불일치하면 충돌을 알리며 새 경로 계산만으로 이동, 생성, clone하지 않는다. 별도 workspace 경로는 관리 도구의 결과를 사용한다.
- 쓰기 전 실제 경로와 symlink 대상을 확인한다. 서로 다른 문서 소속의 경로가 같거나 포함 관계이면 충돌로 처리한다. assets와 문서 경로도 분리한다. 문서의 코드 repo 내부 배치는 document의 팀 공유 또는 명시 요청 예외를 확인한다.

외부 skill의 배포 선택은 common/base/dependencies.toml과 제품별 선언이 소유한다. 제거한 제외 관리 초안의 kit.data 필드는 새 설정으로 이관하지 않는다. 기존 설정 파일에 해당 값이 있으면 원본은 보존하고 새 규격 전환에서 사용하지 않는 항목으로 표시한다. 이 설정은 문서와 코드 위치의 연결이며 설치나 동기화를 자동 실행하지 않는다.

### 동기화 정책 해석

1. project/group/common은 소속의 `sync` table이 있으면 그 table 전체를 사용한다. 없으면 `documents.sync`, 그것도 없으면 꺼짐 정책을 사용한다. 개인 knowledge는 `knowledge.sync`만 사용하고 없으면 꺼짐이다. 선택한 table의 생략 필드는 위 기본값을 사용하며 상위 table과 항목별 병합하지 않는다. 아래 검증 규칙은 개인 knowledge에도 적용한다.
2. `targets`의 모든 식별자가 정의돼 있는지 확인한다. 정의만 된 대상은 허용 대상으로 추가되지 않는다. 동기화 연결을 검증할 때 문서의 실제 경로를 포함하는 Git 작업 트리의 최상위 경로가 각 대상의 `repository`와 일치하고, 해당 저장소에 `remote`가 등록돼 있는지 확인한다. symlink와 중첩 저장소를 고려해 실제 Git 경계를 확인하며 단순 경로 접두어로 판정하지 않는다. 불일치하면 동기화를 보류한다. 이 버전은 해당 저장소의 직접 Git 동기화만 다루며 다른 저장소로 복사하는 방식은 별도 계약이 필요하다.
3. `exclude`는 비어 있지 않은 `/` 구분 상대경로다. 절대경로, `.`/`..` 구성요소, 역슬래시와 glob은 허용하지 않는다. 해당 경로 자체와 디렉터리일 때 그 하위를 제외하며 `private`가 `private-old`까지 일치하지는 않는다. symlink로 소속 밖 자료를 포함하지 않는다.
4. 정책은 소속 문서에만 적용한다. 코드, assets, config를 자동으로 포함하지 않는다. Git 저장소 전체의 현재 추적 파일과 전송될 이력에 비허용 자료가 포함되는지도 확인해야 한다. `enabled=false`나 `exclude`는 untrack, 이력 정리 또는 부분 push를 구현하지 않는다.
5. 실행 도구가 허용 대상과 제외 범위를 보장하지 못하면 전송을 보류한다. 저장소 분리나 별도 수단이 필요한 조건으로 알리고 자동 이관하지 않는다. 설정의 허용 범위와 실제 외부 전송 승인은 별개다.

## 제약과 주의점

secret과 credential 원문을 받는 필드는 없다. 인증은 대상 저장소의 기존 인증 수단을 사용하고 이 파일에 복사하지 않는다. 별도 비밀값 참조 필드가 필요하면 저장 방식과 소비자 지원부터 설계한다. 필드 검사만으로 값 속 비밀정보 탐지를 보장하지 않는다.

## 결과와 완료 판단

설정 검증 결과에 선택한 파일과 버전, 필드 오류, 소속별 유효 경로와 정책, 충돌 및 미확인 연결을 구분한다. TOML 파싱 성공은 의미 검증이나 실제 소비자 지원의 증거가 아니다.

## 예시

[config.example.toml](../assets/config.example.toml)은 최소 시작값과 선택 항목 예시다. 주석 예시는 필요한 것만 선택해 실제 값으로 바꾼다. 예시 경로가 존재하거나 접근 가능한 것으로 간주하지 않는다.
