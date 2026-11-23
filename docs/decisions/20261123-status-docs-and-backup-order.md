# A-04/A-05 현재·이력 구분과 백업 목차 교정

## 요청과 범위

2026-11-23 사용자는 직전 제시한 ‘4번: 현재·과거 상태 문서 정리와 개인 백업 skill 목차 교정’에 ‘ㄱㄱ’로 진행을 요청했다. 공통/private scratch의 관련 문서와 개인 백업 지침만 수정했다. 기존 운영 source·설치본·설정·자료·역할·pin·실행기·timer와 외부 공식 설치본은 변경하지 않았다. 후속5번의 새 제품 조립·계약 정렬/통합 검증과6번 운영 적용은 실행하지 않았다.

## 발견과 교정

| 대상 | 확인한 불일치·혼동 | 교정과 보존 |
| --- | --- | --- |
| architecture.md | private native 구현 설명과 ‘아직 미결’, 초기39/44/47개 트리와 ‘현재’ 표현이 혼재 | 현재 책임/남은 범위와 단계별 구조 이력 분리. 초기 트리·수치·미실행은 당시 기록으로 보존. private source/native 별도 계약과 실제 package/lifecycle 파일 배치 반영 |
| requirements.md | R-02/R-06/R-07/R-12 등 반영 열에 후속 구현 전의 미실행/미구현이 현재처럼 남음 | 기존 요구 문장·ID를 보존하고 현재 근거와 잔여 범위 연결. R-14는 사용자 작성·검수 요청 이력으로 구분하며 전체 문안 승인을 새로 주장하지 않음. 공통 표 렌더링을 위해 동일 표 행을 연속 배치 |
| verification.md | 여러 시점의 ‘현재 범위/최신’과 상단 최신 결과가 중첩 | 양쪽 문서에 현재 요약과 구분된 검증 이력 배치. 기존 결과·실패·수치·제한을 삭제하지 않으며 초기 ‘상단 표는 현재’ 표현만 당시 상태로 명확히 함 |
| migration-status.md·provider-status.md | 과거 권장 순서와 당시 미구현 표가 현재 실행 대기처럼 보임 | 현재 후속 순서/근거와 이력 분리. BMAD 공식 수정본 보완·자동 update404 미지원·기존 운영 hook 차단을 구분. 원래 도입 구상/PTBMAF·Design Doc·Obsidian·NotebookLM 유지 |
| private artifact-backup | SKILL과 연결된 transition reference 모두 ‘실패와 복구’가 ‘결과와 완료 판단’ 앞에 위치 | 두 파일의 해당 절 순서만 뒤바꿈. metadata·절별 내용·명령·보존/권한·보고 표·reference 경로 유지 |

본문 보존과 현재 반영 위치의 상세는 개인 scratch의 `docs/decisions/20261123-backup-heading-order.md`에 연결한다. 상세 저작 기준을 docs에 복제하거나 새 실행 절차를 만들지 않았다.

## 배치와 읽기 관계

새 업무 skill·hook·script는 없다. 기존 docs와 기존 백업 skill/reference를 수정하고 양쪽 결정 기록1개씩을 추가했다.

```text
common source/docs/
  architecture · requirements · verification · migration-status
  provider-status · README · decisions/<이번 기록 및 감사 후속>
private source/
  docs/architecture · requirements · verification · decisions/<목차 교정 기록>
  common/base/skills/artifact-backup/
    SKILL.md · references/transition.md
```

```text
문서 독자 → 현재 구조/요구/판정/후속 순서 → 필요한 당시 결정·검증 이력
백업 요청 → 기존 artifact-backup 본문 → 전환 요청이면 기존 transition reference
           → 기존 실행기/가드/검사 계약 (이번 변경 없음)
```

## 검수와 한계

기존 `plugin-authoring`의 kit 작성·skill 작성/감사와 공식 system `skill-creator`의 좁은 수정·보존/형식 절차를 적용했다. 목차 순서 정렬이므로 본문 분량·발동·선택·연결 의미를 새로 설계하지 않았다. 새 모델 행동·압축/재개·제품 설치 시험을 추가하지 않는다. 동일 작성자의 정적 검수이며 독립 감사가 아니다.

검수는 두 차례로 구분한다. 첫 대조에서는 요구 문장/ID·절별 원문·기존 검증/이관 기록 보존과 변경 scope를 확인한다. 두 번째에서는 현재 요약의 주요 완료/미결을 실제 source와 이전 증거에 대조하고, 상대 링크/anchor·목차·metadata·공식 형식을 확인한다. 코드 전체 회귀나 과거 native 시험을 오늘 재실행한 것으로 보고하지 않는다. 기계적 문자/링크 일치만으로 문서 의미의 완전성이나 과거 요구 전체 대조를 주장하지 않는다.

새 공통 후보와 private exact pin은 여전히 불일치한다. A-03의 Claude 분량 위반·기존 운영 hook 차단, 자동 update404 미지원·실자료/운영 미검증을 해결 상태로 바꾸지 않았다. A-04/A-05의 이번 교정 범위와 kit 전체 적합/운영 전환을 구분한다.

상세 변경 전 파일·hash·정적 대조·공식 형식 결과는 로컬 `/data/projects/_scratch/tr-kit-doc-alignment-20261123/`에 보존한다. 로컬 상세 로그/시험 자료는 kit 배포 구성에 추가하지 않는다.

### 실제 확인한 결과

- 백업 SKILL3741자·전환 reference4334자로 각각 전후 동일하고, metadata/prefix와 모든 절 본문·각 줄의 다중집합이 동일했다. 표준 목차 순서도 두 파일 모두 일치한다.
- 공식 system skill-creator의 `quick_validate.py`로 artifact-backup 기초 형식을 확인해 통과했다. 의미·실행/모델 행동 검사와 구분한다.
- 기존 공통48개·개인19개 요구의 ID/요구 문장을 유지하고 이번 연결 R-49/P-20만 추가했다. R-14 외 기존 공통 합의 상태는 유지했다.
- 양쪽 verification과 공통 migration-status의 기존 본문 전체를 재대조했다. 계층/당시 상태를 명시한 제목·초기 표 설명 변경 외 결과·실패·조건은 보존됐다.
- 두 번째 정적 검수에서 현재 요약의 주요 항목을 앞선 결정·현재 source/pin/파일 배치와 대조했다. 공통53/private9 skill, 앞선 공통 최종 지침 hash와 역할/계약 보존을 확인했다. 모든 문장의 의미가 자동 검증됐다는 주장은 아니다.
- 양쪽 docs와 백업 지침의 로컬 파일/anchor135개를 대조해 누락0이었다. 변경14파일을 명시 payload로 선택해 기존 Gitleaks 기반 비밀 검사에서 pass를 확인했다. 링크 검사는 외부 웹 문서 최신성 검사나 모든 Markdown 렌더러의 의미 검증이 아니다.
