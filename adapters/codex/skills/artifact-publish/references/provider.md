# Codex — 공식 Sites 연결

## 목적과 역할 경계

- artifact-publish가 선택한 Codex 게시 연결이다. 내용·계정·범위·전송 검사·완료 판단은 공통 skill을 따르고 공식 Sites 절차를 복제하지 않는다.

## 입력과 전제

- 공통에서 받은 최소 전송 파일·제목·기존 project_id/URL·승인 audience와 kit root, 명시 provider 선언을 사용한다. 기존 ID와 audience를 유지하며 중복 Site를 만들지 않는다.
- 현재 세션의 공식 Sites SKILL.md와 필요한 native 도구가 실제 있어야 한다. 도구 발견은 실행·설치·공개 범위 승인이 아니다.

## 수행 방법과 절차

1. 아래 외부 연결 계약으로 공식 sites SKILL.md에 진입한다. 실제 요청이 정적 문서/도표이면 공식 buildless static 경로를 사용하고 사이트 동작·서버 기능을 임의로 추가하지 않는다.
2. 새 Site 작업은 필요한 파일만 담은 독립 작업 폴더, 기존 Site는 지정된 실제 ID를 사용한다. 등록·source helper·Git/credential·packaging·게시·재개 절차는 공식 지침의 해당 경로를 따른다. 기존 프로젝트 전체를 게시 source로 삼지 않는다.
3. 실제 계정/audience와 payload가 공통 승인·검사 범위에 맞는지 대조한다. 원문 관리 helper를 복제하거나 임의 Git 인증·업로더를 만들지 않는다. source helper의 commit/push는 선택한 Site 작업 폴더에 한정해 영향 범위를 확인한다.
4. 공식 반환 URL·terminal 배포 상태와 접근 설정을 확인한다. 등록/저장만 된 상태와 배포 완료를 구분하고 기존 deployment의 진행을 이어간다. private 배포 API 성공과 로그인한 사용자의 본문/렌더 확인을 구분한다.

## 연계와 의존

| 대상 | 전달 입력·필요 결과 | 필수 여부·부재 처리 |
| --- | --- | --- |
| provider `sites` · 종류 skill. [공통 외부 연결](../../../../../common/base/references/external-connection.md) | 최소 source·제목·기존 ID/URL·계정/공유 범위. 결과는 실제 URL·배포/저장 상태·권한/접근과 확인 한계 | 필수. 공식 지침/native 도구 부재·조직 거부·비밀 검사 충돌은 게시 보류. 다른 제품·공개 링크로 자동 전환하지 않음 |

## 결과와 완료 판단

- 실제 게시·요청 audience 보존·계정 접근·브라우저 렌더를 각각 보고한다. 현재 비용/포함량을 질문받으면 공식 최신 근거를 확인하며 영구 무료를 약속하지 않는다.
