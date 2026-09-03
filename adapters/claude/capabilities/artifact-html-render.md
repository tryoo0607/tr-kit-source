Claude에서는 자체완결 HTML 파일을 작성한 뒤 **Artifact로 렌더·발행**한다. 같은 산출물을 수정할 때는 기존 Artifact를 갱신하고, 공개 URL·favicon 같은 발행 식별자는 프로젝트 기록의 값을 유지한다. CSP를 고려해 원격 이미지·임의 CDN 대신 인라인 또는 `data:` 자원을 사용한다.
