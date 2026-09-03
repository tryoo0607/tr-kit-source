# 로그 소스별 접근 (방법 지침)

**관련 구간만** 수집(시간·레벨·키워드). 전체 덤프는 컨텍스트·시간 낭비.

## 로컬 앱
- 위치: 프레임워크/설정 따라(`logs/`, `stdout`, `~/.<app>/`). 실행 로그면 stdout/stderr.
- 필터: `grep -i error`, 최근 N줄 `tail -n 200`, 실시간 `tail -f`.

## 서버 (systemd / 파일)
```bash
# systemd 서비스
journalctl -u <svc> -n 200 --no-pager        # 최근 200줄
journalctl -u <svc> --since "10 min ago"
journalctl -u <svc> -p err                    # 에러 이상만
journalctl -k                                 # 커널
# 파일 로그
sudo tail -n 200 /var/log/<file>
```
- 원격: `ssh <host> 'journalctl -u <svc> -n 200'` (대상·경로는 해당 인프라 inventory). 실행은 확인 후.

## 컨테이너
```bash
docker logs --tail 200 -f <container>
docker logs --since 10m <container>
kubectl logs <pod> [-c <container>] --tail=200 [-f] [--previous]   # --previous=크래시 직전
```

## IntelliJ
- IDE 로그: **Help > Show Log in Explorer/Finder** → `idea.log`. 최근 에러·스택.
- 앱 실행 콘솔: Run/Debug 창 출력(직접 붙여넣기).

## 분석 포인트
- **최초 실패 지점**(맨 처음 에러 — 뒤 에러는 파생일 때 많음).
- **스택트레이스** 최상단 원인 프레임.
- **타임라인**: 언제부터·주기·상관 이벤트.
- **반복 패턴**: 같은 에러 빈도, 특정 입력·시간대.

## 주의
- **secret 마스킹**: 로그에 토큰·비번 있으면 가리고 다룸(→ `secrets`).
- 결과(원인 후보·재현 조건)는 디버그 지침로, 회귀는 `project`로.
