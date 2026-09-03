#!/usr/bin/env python3
"""tr-kit-source transform — 블록가드 스트립 + 토큰 치환, fail-closed.

한 타깃의 skills/ 트리를 읽어 out/<target>/ 로 낸다.
- 블록가드: <!-- if:claude -->...<!-- /if -->  (comma로 다중타깃 `if:claude,codex`)
- 토큰:     {{VAR}}  ->  glossary/<target>.toml 값
- fail-closed: glossary가 _schema 토큰을 빠뜨리거나, 산출물에 미치환 {{ 가 남으면 실패.
"""
import argparse
import re
import sys
import tomllib
from pathlib import Path

GUARD = re.compile(
    r'[ \t]*<!--\s*if:([\w,]+)\s*-->[ \t]*\n(.*?)[ \t]*<!--\s*/if\s*-->[ \t]*\n?',
    re.DOTALL,
)
# 토큰은 대문자 식별자만(AGENT_FILE 등). GitHub Actions `${{ secrets.X }}`
# 같은 소문자·점 표현식과 충돌 안 나게 좁힌다 → GHA 문법은 산출물에 그대로 보존.
TOKEN = re.compile(r'\{\{\s*([A-Z][A-Z0-9_]*)\s*\}\}')
LEFTOVER = re.compile(r'\{\{\s*[A-Z][A-Z0-9_]*\s*\}\}')

# 이 확장자만 텍스트로 취급(블록가드+토큰). 나머지는 바이트 복사.
TEXT_EXT = {'.md', '.sh', '.json', '.toml', '.yaml', '.yml', '.txt'}


def die(msg: str) -> None:
    sys.exit(f'FAIL: {msg}')


def load_glossary(gdir: Path, target: str) -> dict:
    schema = tomllib.loads((gdir / '_schema.toml').read_text())
    keys = set(schema.get('tokens', {}).keys())
    tf = gdir / f'{target}.toml'
    if not tf.exists():
        die(f'glossary/{target}.toml 없음')
    vals = tomllib.loads(tf.read_text())
    missing = keys - set(vals)
    extra = set(vals) - keys
    if missing:
        die(f'[{target}] _schema 토큰 누락 → {sorted(missing)}')
    if extra:
        die(f'[{target}] _schema에 없는 토큰 선언 → {sorted(extra)}')
    return vals


def strip_guards(text: str, target: str) -> str:
    def repl(m: re.Match) -> str:
        targets = [x.strip() for x in m.group(1).split(',')]
        return m.group(2) if target in targets else ''
    return GUARD.sub(repl, text)


def sub_tokens(text: str, vals: dict) -> str:
    return TOKEN.sub(lambda m: vals.get(m.group(1), m.group(0)), text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True)
    ap.add_argument('--src', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--glossary-dir', required=True, type=Path)
    a = ap.parse_args()

    vals = load_glossary(a.glossary_dir, a.target)
    n = 0
    for f in sorted(a.src.rglob('*')):
        if f.is_dir():
            continue
        rel = f.relative_to(a.src)
        out = a.out / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix in TEXT_EXT:
            text = sub_tokens(strip_guards(f.read_text(), a.target), vals)
            left = LEFTOVER.findall(text)
            if left:
                die(f'[{a.target}] 미치환 토큰 {left} in {rel}')
            out.write_text(text)
        else:
            out.write_bytes(f.read_bytes())
        out.chmod(f.stat().st_mode)   # 실행비트 보존(.sh 훅)
        n += 1
    print(f'  [{a.target}] {n} files -> {a.out}')


if __name__ == '__main__':
    main()
