---
name: logs
description: 애플리케이션·서버·IDE·컨테이너 로그를 찾아 읽고 분석할 때 사용한다. "로그 봐줘", "이 오류 로그 분석".
---

# logs

로그를 **찾아·읽어·분석**한다. 에러·스택트레이스·타임라인·패턴을 뽑아 디버그 지침(원인 추적)에 넘긴다. **로그 = 재료, 원인 규명 = debug.**

## 대상 소스
| 소스 | 접근 |
|---|---|
| 로컬 앱 로그 | 파일 경로 · stdout/stderr |
| 서버 (systemd) | `journalctl -u <svc>` · `/var/log/…` · `tail -f` |
| 컨테이너 | `docker logs` · `kubectl logs`(+`-f`,`--previous`) |
| IntelliJ | `idea.log`(Help>Show Log) · 실행 콘솔 |

상세 접근·필터 = `references/sources.md`.

## 절차
1. **소스 특정**: 어떤 로그인지·어디 있는지(대상 서버는 설치된 도메인 plugin의 inventory 참조).
2. **수집**: 관련 구간만(시간·레벨·grep). 전체 덤프 지양.
3. **분석**: 에러·스택·최초 실패 지점·타임라인·반복 패턴 추출.
4. **넘김**: 원인 추적은 디버그 지침, 재발 방지 케이스는 `project`.

## 경계
- **원인 규명·수정 = 디버그 지침** (로그는 그 재료).
- 서버 접속은 해당 인프라의 inventory·접속 규약을 먼저 확인한다. 원격 실행은 확인 후.
- 로그에서 **secret 발견 시** → 마스킹, `secrets` 연계(로그에 secret 남기지 않기).
