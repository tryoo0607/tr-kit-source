#!/usr/bin/env bash
# The runner owns all checkouts and SSH configuration below this temporary root.
set -euo pipefail
marketplaces=$1
scanner=$2
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
: "${TR_CODEX_DEPLOY_KEY:?Codex deploy key missing}"
: "${TR_CLAUDE_DEPLOY_KEY:?Claude deploy key missing}"
umask 077
printf '%s\n' "$TR_CODEX_DEPLOY_KEY" > "$temp/codex-key"
printf '%s\n' "$TR_CLAUDE_DEPLOY_KEY" > "$temp/claude-key"
unset TR_CODEX_DEPLOY_KEY TR_CLAUDE_DEPLOY_KEY
curl --fail --silent --show-error --proto '=https' https://api.github.com/meta |
  jq -er '.ssh_keys[] | "github.com " + .' > "$temp/known_hosts"
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$temp/known_hosts"
root=$PWD

assert_current_main() {
  local remote_head
  remote_head=$(git ls-remote https://github.com/tryoo0607/tr-kit-source.git refs/heads/main | cut -f1)
  if [[ "$remote_head" != "$GITHUB_SHA" ]]; then
    echo 'Source main advanced before publication.'
    exit 1
  fi
}

assert_current_main
for product in codex claude; do
  repo="$temp/tr-$product"
  git clone --single-branch --branch main "https://github.com/tryoo0607/tr-$product.git" "$repo"
  rsync -a --delete --exclude='/.git/' "$marketplaces/$product/" "$repo/"
  jq -n --arg path "$repo" --arg gitleaks "$scanner" \
    '{gitleaks:$gitleaks,repositories:[{path:$path,local_only:[],allow_artifacts:[]}]}' > "$temp/$product-policy.json"
  git -C "$repo" add --all --force
  python3 -B "$root/scripts/check-git-secrets.py" index --repo "$repo" --policy "$temp/$product-policy.json"
  if git -C "$repo" diff --cached --quiet; then
    continue
  fi
  git -C "$repo" -c user.name='github-actions[bot]' \
    -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit -m "build: publish tr-kit-source $GITHUB_SHA"
  git -C "$repo" remote set-url --push origin "git@github.com:tryoo0607/tr-$product.git"
  printf 'refs/heads/main %s refs/heads/main %s\n' \
    "$(git -C "$repo" rev-parse HEAD)" "$(git -C "$repo" rev-parse origin/main)" |
    python3 -B "$root/scripts/check-git-secrets.py" push --repo "$repo" --policy "$temp/$product-policy.json"
  GIT_SSH_COMMAND="$GIT_SSH_COMMAND -i $temp/$product-key" git -C "$repo" push --dry-run origin HEAD:main
done

for product in codex claude; do
  repo="$temp/tr-$product"
  assert_current_main
  if [[ "$(git -C "$repo" rev-parse HEAD)" != "$(git -C "$repo" rev-parse origin/main)" ]]; then
    GIT_SSH_COMMAND="$GIT_SSH_COMMAND -i $temp/$product-key" git -C "$repo" push origin HEAD:main
  fi
  test "$(git -C "$repo" rev-parse HEAD)" = "$(git -C "$repo" ls-remote origin refs/heads/main | cut -f1)"
done
