---
name: ext-write-design-docs
description: 기술 PoC 실측 근거와 기술 대안을 채택 판단용 보고서로 작성·갱신하거나 검토할 때 write-design-docs에 연결한다.
metadata:
  tr-role: external-wrapper
---

# ext-write-design-docs

## 목적과 역할 경계

- PoC의 관측 결과와 대안을 읽을 수 있는 기술 선택 보고서로 정리할 때 외부 `write-design-docs`를 적용한다. 실험이나 채택 승인은 별도 업무다.

## 입력과 전제

- 검증 질문, 버전과 환경, 관측 결과와 출처, 확인하지 못한 범위, 비교할 대안, 보고서 독자와 기존 문서 위치.

## 수행 방법과 절차

1. 아래 공통 외부 연결로 검수된 원본에 진입한다. 필요한 가이드와 문서 길이는 원본 절차에서 선택한다.
2. 보고서에서는 실측 사실과 추론을 구분하고 대안, 비용, 채택·추가 검증·보류 권고의 근거를 보여준다. 기존 PoC 문서가 있으면 허용된 범위에서 해당 문서를 갱신하고 판단이 바뀐 이유를 남긴다.
3. 근거가 모자라면 어떤 검증이 필요한지 표시한다. 실험 실행 요청은 기술 PoC의 범위 확인에 연결한다.

## 연계와 의존

| 대상 | 전달 입력·필요 결과 | 필수 여부·부재 처리 |
| --- | --- | --- |
| [공통 외부 연결](../../references/external-connection.md)의 `write-design-docs` · 종류 `skill` | 위 입력을 [pproenca의 write-design-docs](https://github.com/pproenca/dot-skills/tree/cf93c57cac89d6fc3e4194686000411567f5caf3/skills/.experimental/write-design-docs)에 전달한다. 기술 대안과 선택 근거를 검토할 보고서를 얻는다. | Codex와 Claude에서 실제 진입점과 필수 가이드의 설치본 검수가 필요하다. 확인할 수 없으면 해당 작성 단계를 보류한다. |

## 결과와 완료 판단

- 보고서의 권고를 실제 관측과 대조하고, 관측할 수 없었던 범위와 추가 검증을 표시한다. 작성하거나 갱신한 위치 및 외부 연결의 검수 범위를 전달한다.
