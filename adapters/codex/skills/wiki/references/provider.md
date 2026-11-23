# codex — 공식 Wiki 연결

## 목적과 역할 경계

- 공통 wiki의 요청 동작을 제품 공식 설치본에 연결한다. hub 구조·검색·수집·복구 절차를 복제하지 않는다.

## 입력과 전제

- 공통에서 동작·hub/topic·소속·승인 범위와 명시 provider 선언을 받는다. 실제 사용 제품은 codex다.
- [공통 외부 연결](../../../../../common/base/references/external-connection.md)로 선택한 entry 하나만 resolve한 후 공식 SKILL.md를 읽고 적용한다. 선언 파일/원문 존재만으로 native 호출 성공을 주장하지 않는다.

## 수행 방법과 절차

| 요청 | 선택 조건 | 읽을 reference |
| --- | --- | --- |
| 질문·검색·조회만 | 쓰기/수집 요청 없음 | provider `wiki-query` · 종류 skill의 공식 SKILL.md |
| 수집·compile·갱신·관리 | 해당 변경이 명시 요청/승인에 포함 | provider `wiki` · 종류 skill의 공식 SKILL.md |

- 같은 요청은 첫 일치 하나, 별도 요청은 각각 평가한다. 조회는 공식 wiki-query의 읽기 전용 계약을 적용하며 색인 재생성·query log·lint를 실행하지 않는다. stale는 알리고 허용한 원문을 확인한다.
- 관리 원문이 읽기 중 색인 재생성 등 변경을 요구하면 실제 효과를 승인 범위와 대조한다. 이 충돌을 원문 치환/새 runtime/관리 명령 우회로 해결하지 않는다. 영향받는 변경만 보류한다.

## 결과와 완료 판단

- 선택한 provider·실제 조회/변경·source·미확인을 공통에 반환한다. 해당 공식 설치본이 없으면 미연결로 알리며 설치·업데이트·수집을 자동 실행하지 않는다.
