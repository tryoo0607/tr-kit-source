# G7: 공식 설치 근거·리소스·업데이트 검수 연결

2026-11-18 후속 진행 요청에 따라 scratch source를 보완했다. 운영 설치·신뢰 승인·자료/worker/timer·기존 설정·원격 전송을 실행하는 단계와 구분한다.

## 문제와 채택한 연결

기존 resolver는 선택 entry·제품 선언·hash를 확인했다. entry 밖의 reference·template·script가 변하거나 설치 근거가 미확인인 상태를 구분할 추가 검수가 필요했다. 공식 설치와 업무 절차는 기존 공식 manager/skill에 맡기고, 자체 코드는 명시 설치 디렉토리의 파일 명세·설치 근거 hash·제품 검수 기록을 대조한다. 새 설치기·원문 변환기·범용 workflow 엔진을 만들지 않는다.

```text
common/base/
  references/external-connection.md ──조건부 참조──> provider-review.md [추가]
  scripts/provider_links.py         entry pin (기존)
  scripts/provider_review.py        설치 명세·근거 대조/업데이트 차이 [추가]
  scripts/claude_mem.py             start/MCP 직전 검수 [변경]
scripts/provider-review.py          own CLI [추가]
private/common/base/scripts/
  common_links.py ──pin 확인/호출──> 공통 provider-review CLI [변경]
  private_runtime.py                명시 provider_reviews 경로 검증 [변경]
  common-contract.toml              검토한 새 source-bundle pin [변경]
```

실행 흐름은 wrapper → entry 확인 → 선택 설치본 검수 → 공식 절차 진입이다. 위 트리는 파일 배치와 호출 관계를 표시하며 native 자동 발견·상시 hook 연결을 뜻하지 않는다. 새 hook·스킬 metadata·private→공통 구현 복사는 추가하지 않았다.

## 검수 상태와 경계

- snapshot은 pending 초안이다. 명시 root의 전체 파일과 설치 근거를 기록하되 공식 출처·필수 외부 의존·제품 계약을 자동 승인하지 않는다.
- verify는 검수 완료 기록의 entry·파일 추가/삭제/변경·근거 bytes와 현재 제품을 다시 확인한다. 출력은 로컬 검수 기록 일치이며 작성자 인증·공급망 서명·실행 성공이 아니다. 검사 후 실행 사이의 변경을 OS 수준으로 봉쇄하지 않는다.
- compare는 이전/새 기록의 리소스·identity·증거·제품 계약 차이를 반환한다. 원문/사본을 저장하거나 문구를 치환하지 않고, 의미 검토·업데이트 승인·repin을 대신하지 않는다.
- 실제 실행 연결에서 필수 미결이 있으면 보류한다. 단순 설치 현황 조사에는 미검수 상태를 그대로 보고할 수 있다. 외부 의존 부재로 독립적인 자료 확인까지 중단하지 않는다.
- Claude-Mem schema2의 reviews 두 개는 start/MCP 실행 전에 검사한다. 구 schema1은 정적 확인용으로 남긴다. 검수 기록의 변동/부재가 소유 worker 중단을 새로 막지 않도록 stop은 기존 소유·runtime·health 검사로 유지한다.
- private Wiki helper도 공통 검사를 재사용한다. 실제 개인 설정에 review 경로를 쓰거나 capture를 켜지는 않았다. REA 독립 admission/runtime과 이 provider 계약은 동일 인터페이스로 가장하지 않으며 실제 공식 REA 환경 검증은 남아 있다.

## 실제 확인과 미결

현재 명시 선언의 Context7 0.8.2와 Playwright CLI 0.1.22는 npm 공식 registry metadata·archive SRI·기존 lock을 대조했고, 설치 package 파일 10개/16개가 각각 archive 전체 파일과 일치했다. 전이 의존·Node/브라우저·native workflow는 이 대조로 완료되지 않았다. snapshot은 pending으로 유지했다. 상세 현재 지원/설치 경로는 [공식 연결 현황](../provider-status.md), 실제 시험은 verification.md에 연결한다.

private의 source-bundle-v1 계약은 G1 이전120파일에서 G1~G7의150파일 source로 검토해 갱신한다. 양 제품 각각 추가30·변경11·삭제0을 기록하고 G1~G6 검증과 새 provider 계약을 대조했다. exact inventory·추가 파일 거부·제품별 pin을 유지한다. 이 변경은 scratch 계약이며 호스트 config.common_root를 이관하지 않는다. native marketplace payload를 source bundle인 것처럼 수용하는 변경은 하지 않았다.

G7 source 보완·격리 검수와 G7 전체 공식 provider 설치/실제 workflow 검증은 별개다. 공식 BMAD/Wiki/시각화/Android 등 설치·Claude native·공통+private native 조합·실제 압축/재개는 아직 완료하지 않았다. 원문 대조 checkout과 구 동봉/치환 설치본으로 빈자리를 채우지 않는다.
