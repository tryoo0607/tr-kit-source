# Contributing

공통 의미와 연결은 common/base, 제품 차이는 adapters, 조립과 검증은 scripts에서 수정한다. 생성된 out을 직접 고치지 않는다. 외부 원본은 고정 commit을 유지하고 지원 자료와 라이선스를 함께 검토한다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/fetch_sources.py
./build.sh codex --output out/codex-review
./build.sh claude --output out/claude-review
git diff --check
```

각 skill은 scripts/validate.py로 포함한 skill-creator 기준에 대조한다. CI는 두 제품을 검증하며 main에 반영하면 delivery workflow가 기존 두 배포 저장소를 갱신한다. 배포 세부 계약과 dry-run은 README를 따른다. source/조립 검증과 native host 등록, 모델의 실제 선택 및 CLI 실행은 서로 다른 검증이다.

개인 경로, credential, memory DB나 browser state를 source에 추가하지 않는다. 문서 및 project의 이관은 ROLLOUT.md에 따라 별도 대상으로 검토한다. Codex가 우선 적용 대상이고 Claude의 실제 host 적용은 후속이다.
