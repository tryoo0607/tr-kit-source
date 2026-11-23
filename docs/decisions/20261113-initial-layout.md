# 임시 작업 공간에서 합의 내용부터 작성

2026-11-13 사용자가 scratch에 임시 tr-kit-source를 만들고 하나씩 작성하자고 요청했다. 호스트의 임시 프로젝트 관례인 _scratch를 사용한다.

기존 설치본과 소스를 복사해 수정하는 대신, 합의한 구조·요구를 문서로 작성하고 필요한 지침·구현을 순차 작성한다. 원격 연결·기존 설치본 교체·배포는 이 초기 준비에 포함하지 않는다.

docs 하위 구성은 README.md, requirements.md, architecture.md, decisions/, verification.md로 사용자가 확정했다. 요구 목록은 상세 기준을 복제하지 않고 근거·상태·반영 위치를 보여준다.

## 저작·감사 진입점 명칭 변경

사용자는 상위 진입점과 내부 kit 대상의 구분을 위해 plugin-authoring 명칭을 채택하고 수정을 요청했다. 기존 kit-authoring 디렉토리·frontmatter·제목·현재 문서 참조를 plugin-authoring으로 변경했다. 담당 범위는 kit·skill·hook의 작성·수정·감사로 유지하며 실제 설치·배포 실행 역할을 추가하지 않았다.
