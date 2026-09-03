# Contributing

기여는 fork에서 브랜치를 만든 뒤 pull request로 제출한다. `main`에 직접 push하지 않는다.

## 변경 원칙

- 공통 의미와 정책은 `core/`, Claude·Codex 종속 형식과 기능 연결은 `adapters/<target>/`에 둔다.
- target별 조립은 `recipes/<target>.toml`에 선언하며 생성된 `out/`은 커밋하지 않는다.
- public source에 개인 경로, 장비명, 저장소명, 자격증명 또는 private plugin 전용 key를 넣지 않는다.
- 동작 변경에는 같은 실패를 재현하고 막는 테스트를 포함한다.

## 검증

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
./build.sh
bash tests/hooks/lifecycle-smoke.sh
git diff --check
```

가능하면 `gitleaks dir . --no-banner`도 실행한다. Pull request에는 변경 이유, 영향받는 target,
검증 결과와 호환성 영향을 적는다.
