# 선택한 산출물의 전송 비밀 검사

## 목적과 역할 경계

- Git 추적 여부와 무관한 실제 전송 payload를 공식 Gitleaks와 기존 공통 scan 함수로 검사한다. 새 탐지 규칙·업로더·게시 기능을 구현하지 않는다.
- kit 외 일반 문서의 전송 비밀 검사이며 외부 원문 보호 catalog를 모든 자료 보관/게시의 금지 기준으로 확대하지 않는다.

## 입력과 전제

- 승인된 내용·저장/공유 범위와 필요한 파일만 담은 명시 payload 폴더를 받는다. 전체 repo/홈을 편의상 검사·업로드 대상으로 삼지 않는다.
- common/base/scripts/secret-tools.toml과 기존 신뢰 receipt의 Gitleaks를 사용한다. 부재는 자동 설치로 해결하지 않는다.

## 수행 방법과 절차

1. 실제 kit root에서 `python3 -B scripts/check-artifact-secrets.py --root /absolute/expanded-payload`를 실행한다. 대상 파일은 읽기만 하며 scanner가 사용하는 자체 비공개 임시 파일은 기존 scan 함수가 만들고 정리한다.
2. 현재 bytes와 파일명을 검사하며 숨김/ignored 파일도 포함한다. symlink/특수 파일·압축 컨테이너는 인증하지 않는다. 최대4096노드·총16MiB, scanner의 기존 timeout을 넘거나 불완전하면 unavailable다. 큰 payload를 조용히 나눠 한도를 우회하지 않는다.
3. 전후 inventory/bytes drift를 검사한다. pass는 관측한 파일의 무탐지 결과다. 발견은 finding, 오류/부재/한도/변경은 unavailable이며 둘 다 exit2다. 원문·파일명은 오류/발견 출력에 넣지 않는다. unavailable 진단은 inventory/scanner-identity/scanner/recheck 단계와 권한·부재·timeout 등 고정 분류만 제공한다.
4. 검사 뒤 파일·이름·패키지 범위가 바뀌면 실제 전송 전에 재검사한다. 다른 process 쓰기를 원자적으로 막는 도구가 아니며 과거 fingerprint를 완료 인증서로 재사용하지 않는다.

## 결과와 완료 판단

- pass/finding/unavailable·파일 수·현재 fingerprint·안전한 규칙/건수와 한계를 반환한다. 무탐지는 공개 허가나 모든 binary/인코딩 비밀의 부재를 보장하지 않는다. 실제 게시·계정/접근 검증은 호출자가 별도로 수행한다.
