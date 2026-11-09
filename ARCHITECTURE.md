# kit 구성과 검증 경계

이 문서는 현재 소스의 구조 설명이다. 경로·명령·버전의 정본을 대체하거나 새로운 runtime 정책을 만들지 않는다. 제품별 파일 집합은 조립 결과에서 확인한다.

## 조립과 적용 흐름

| 단계 | 입력과 담당 | 결과와 확인 근거 |
|---|---|---|
| 외부 source 확보 | sources.toml, dependencies.toml, fetch_sources.py | 정확한 commit의 clean checkout; 자동 reset 없음 |
| 공통 구성 | common/base의 자체 지침·skill·binding과 외부 include | 업무 기준과 기존 외부 기능 연결 |
| 제품 조립 | adapters/<product>와 build.py | 제품별 metadata·MCP·hooks 및 전체 payload의 assembly.json |
| 배포물 생성 | package.py와 delivery.py | marketplace, release.json, source revision과 파일 hash |
| 게시 | build.yml / delivery.yml | 기존 두 배포 repo에 생성물 게시; 제품별 성공 확인 |
| 호스트 설치 | native 제품 CLI와 ROLLOUT.md | 실제 selector·버전·경로·캐시·다른 설정 보존 확인 |
| runtime 활성화 | 제품 trust, 새 세션, 등록된 Git hooks | 실제 callback·가드·도구 실행 근거; 설치 사실과 분리 |

외부 원본의 내부 동작은 upstream이 소유한다. binding은 제품 표현과 선택·연결의 차이를 담당한다. 기능이 같다는 이유로 외부 절차를 자체 사본으로 관리하지 않는다.

## 공통과 private

| 영역 | 소유 책임 | 경계 |
|---|---|---|
| 공통 kit | 개발·조사·자료 보관과 지식 연결·공간·인계·일반 보안 검사 | 개인 인프라 실행기·개인 백업·실제 기기 설정을 포함하지 않음 |
| private kit | 개인 인프라·백업·개인 자료실 연결·REA 환경 관리 | 같은 common/base·adapters·scripts 계층 사용, 공통 기능 복사 금지 |
| private toolchain.lock | 사용할 공통 source commit 고정 | 공통 source는 private에 의존하지 않음 |
| 호스트 설정 | 실제 경로·역할·연결·선택 활성화 값 | 소스나 배포물에 개인 값을 고정하지 않음 |
| 인프라 저장소·데이터 저장소 | 실제 운영 구성·실행기, 원본·사본 | skill source와 운영 데이터·백업을 구분 |

이 표의 private 설명은 연결 계약 수준이다. private의 실제 내용·pin·설치는 해당 저장소와 호스트에서 따로 검증한다. 공통 감사가 private 설치나 회사 자료의 개인 반입을 전제로 해서는 안 된다.

## 업무 간 연결

README 작성·갱신·감사는 외부 github-readme-generator가 소유하고 최종 명령의 구현 조건은 공통 binding에서 보완한다. 전체 kit 감사와 README 자체 검토를 구분한다.

BMAD와 각 업무 skill은 분석·작성·검증을 함께 소유한다. document는 원본 보관·검색·경험·지식 연결에 참여하고 모든 문서의 작성 관문이 되지 않는다. project는 코드 공간, session은 인계와 호스트 운영, Orca는 확인된 조작 수단을 맡는다.

dev01에서 요청을 전달하더라도 수신 호스트의 역할과 가드는 독립적으로 확인한다. 요청 전달 성공을 원격 실행 완료로 간주하지 않으며 조회 승인으로 변경 범위를 확대하지 않는다. 실제 허용 목록의 정본은 private 역할 계약과 호스트 설정이다.

## 상태와 증거

| 주장 | 필요한 근거 | 이것만으로 충분하지 않은 것 |
|---|---|---|
| skill 조립·형식 정상 | include·binding·링크·형식·hash 검사 | 모델이 알맞게 선택한다는 보장 |
| 도구 실행 정상 | 실제 도구 버전과 유효한 입력의 실행 결과 | 도구 이름이나 설치 파일 존재 |
| 설치 완료 | native 설치 목록·payload provenance | 기존 세션의 자동 재로드 |
| Git guard 활성 | 저장소 root·effective hooks·receipt·status와 실제 차단 검사 | plugin 설치만 성공 |
| 제품 hook 활성 | 실제 발견·trust·callback 관측 | hooks.json 존재 |
| 운영 연결 정상 | 승인한 실제 대상에서 조회·응답·검증 | 임시 fixture 또는 합성 모델 응답 |

이전 배포의 성공은 다음 변경의 증거를 대신하지 않는다. 검증 당시 source와 제품·도구 버전, 대상과 시점을 함께 남기며 실패·미확인을 성공에 합치지 않는다.
