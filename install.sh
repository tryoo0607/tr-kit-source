#!/usr/bin/env bash
# tr-kit-source install — 빌드 산출물(out/<target>)을 호스트에 배치.
#   codex  = 마켓플레이스 플러그인 모델(codex plugin marketplace add + plugin add) + AGENTS.md loose.
#   claude = 기존 tr-claude 플러그인 교체(migration) — 라이브 교체는 별도 확인, 스테이징 복사만.
#   happy-host = TEMPORARY_HAPPY_COMPAT host helper + systemd user units.
# 기본은 dry-run(무엇을 할지 출력만). 실제 적용은 --apply. 스테이징은 --dest DIR.
#
#   ./install.sh codex                 # dry-run (실제 ~/.codex 대상)
#   ./install.sh codex --apply         # 실제 설치 (plugin marketplace add + plugin add)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

target="${1:-}"; shift || true
apply=0; dest=""; enable_linger=0; prev=""
for a in "$@"; do
  case "$a" in
    --apply) apply=1 ;;
    --enable-linger) enable_linger=1 ;;
    --dest=*) dest="${a#--dest=}" ;;
  esac
  [ "$prev" = "--dest" ] && dest="$a"
  prev="$a"
done

if [ -z "$target" ]; then
  echo "usage: install.sh <claude|codex|happy-host> [--apply] [--dest DIR] [--enable-linger]"; exit 1
fi
case "$target" in
  claude|codex) [ -d "$ROOT/out/$target" ] || "$ROOT/build.sh" "$target" >/dev/null ;;
esac

codex_home="${dest}${CODEX_HOME:-$HOME/.codex}"

act() { # act "설명" "명령"
  if [ "$apply" = 1 ]; then echo "  ✓ $1"; eval "$2"; else echo "  [dry] $2"; fi
}

echo "== install: $target  (apply=$apply${dest:+  dest=$dest}) =="
case "$target" in
  codex)
    O="$ROOT/out/codex"
    kn="$(python3 -c "import tomllib;print(tomllib.load(open('$ROOT/glossary/codex.toml','rb'))['KIT_REPO'])")"
    [ -f "$O/.agents/plugins/marketplace.json" ] || { echo "  ✗ out/codex 가 마켓 구조 아님 — build.sh codex 먼저"; exit 1; }
    echo "[marketplace] add  ($O)"
    act "codex plugin marketplace add" "codex plugin marketplace add '$O'"
    echo "[plugin] add  $kn@$kn"
    act "codex plugin add" "codex plugin add '$kn@$kn'"
    echo "[AGENTS] → $codex_home/AGENTS.md  (전역 — 플러그인이 안 줌)"
    act "AGENTS.md 복사" "mkdir -p '$codex_home' && cp '$O/plugins/$kn/AGENTS.md' '$codex_home/AGENTS.md'"
    [ "$apply" = 1 ] || echo "  (실제 설치는 --apply)"
    ;;
  claude)
    echo "  claude 설치 = 기존 tr-claude 플러그인 교체(migration)."
    echo "  round-trip 검증됨(out/claude = 원본 파일셋 일치)이나, 라이브 플러그인 교체는 별도 확인 후."
    if [ -n "$dest" ]; then
      act "out/claude → $dest/tr-claude-plugin/" \
        "mkdir -p '$dest/tr-claude-plugin' && cp -r '$ROOT/out/claude/.' '$dest/tr-claude-plugin/'"
    else
      echo "  스테이징: --dest DIR --apply 로 out/claude 를 그 아래 복사만."
    fi
    ;;
  happy-host)
    # TEMPORARY_HAPPY_COMPAT: isolated host support, removed with Happy migration.
    H="$ROOT/host/happy"
    [ -f "$H/happy_cycle.py" ] || { echo "  ✗ missing host helper: $H/happy_cycle.py"; exit 1; }
    host_home="${dest:-$HOME}"
    bin="$host_home/.local/bin/happy-cycle"
    units="$host_home/.config/systemd/user"
    echo "[bin] $H/happy_cycle.py → $bin"
    for unit in "$H/systemd"/*; do echo "[systemd] $(basename "$unit") → $units/"; done
    if [ "$apply" = 1 ]; then
      install -Dm755 "$H/happy_cycle.py" "$bin"
      for unit in "$H/systemd"/*; do install -Dm644 "$unit" "$units/$(basename "$unit")"; done
    else
      echo "  [dry] install -Dm755 '$H/happy_cycle.py' '$bin'"
      echo "  [dry] install -Dm644 '$H/systemd/'* '$units/'"
    fi
    if [ -n "$dest" ]; then
      echo "  staged only — systemd state unchanged"
    else
      act "systemd user daemon-reload" "systemctl --user daemon-reload"
      act "enable Happy daemon at user-manager start" \
        "systemctl --user enable --now happy-daemon.service"
      act "enable periodic Happy session snapshot" \
        "systemctl --user enable --now happy-session-snapshot.timer"
      linger="$(loginctl show-user "$(id -un)" -p Linger 2>/dev/null | cut -d= -f2 || true)"
      if [ "$linger" != "yes" ]; then
        if [ "$enable_linger" = 1 ]; then
          act "enable user linger for boot-before-login" "loginctl enable-linger '$(id -un)'"
        else
          echo "  ⚠ Linger is not enabled; boot-before-login needs --enable-linger."
        fi
      else
        echo "  ✓ Linger=yes"
      fi
    fi
    ;;
  *) echo "unknown target: $target"; exit 1 ;;
esac
echo "done."
