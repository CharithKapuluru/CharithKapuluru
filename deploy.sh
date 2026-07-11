#!/usr/bin/env bash
#
# deploy.sh — put your animated GitHub profile live in one shot.
#
# It creates the special <username>/<username> repo, uploads these files,
# stores your token as the ACCESS_TOKEN secret, pushes, and triggers the
# workflow that renders your real stats.
#
# YOU do only two human-only things:
#   1. Run `gh auth login` once (log in to GitHub) before running this.
#   2. Paste a Personal Access Token when this script asks for it.
#
# Usage:
#   cd into this folder (the one containing today.py), then:
#     bash deploy.sh
#
set -euo pipefail

say()  { printf "\n\033[1;36m==>\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
die()  { printf "\n\033[1;31m  ✗ %s\033[0m\n" "$*" >&2; exit 1; }

# --- 0. sanity checks --------------------------------------------------------
command -v git >/dev/null || die "git is not installed."
command -v gh  >/dev/null || die "GitHub CLI (gh) is not installed.  https://cli.github.com"
[ -f "today.py" ] || die "Run this from the unzipped folder that contains today.py."

if ! gh auth status >/dev/null 2>&1; then
  die "You're not logged in to GitHub CLI. Run:  gh auth login   then re-run this script."
fi
ok "git, gh, and login all present."

# --- 1. figure out the username & repo --------------------------------------
USERNAME="$(gh api user --jq .login)"
[ -n "$USERNAME" ] || die "Could not read your GitHub username."
REPO="$USERNAME/$USERNAME"
say "Target profile repo: $REPO"

# --- 2. create the repo (skip if it already exists) -------------------------
if gh repo view "$REPO" >/dev/null 2>&1; then
  ok "Repo $REPO already exists — will push into it."
else
  say "Creating public repo $REPO ..."
  gh repo create "$REPO" --public --description "My auto-updating profile card" >/dev/null
  ok "Repo created."
fi

# --- 3. store the token as a secret (BEFORE the push, so first run has it) ---
say "Now paste a Personal Access Token (classic) with scopes: repo + read:user"
echo    "   Create one at: https://github.com/settings/tokens  (Generate new token, classic)"
printf  "   Token (input hidden): "
read -rs TOKEN
echo
[ -n "$TOKEN" ] || die "No token entered."
printf '%s' "$TOKEN" | gh secret set ACCESS_TOKEN --repo "$REPO"
unset TOKEN
ok "ACCESS_TOKEN secret saved to $REPO."

# --- 4. commit & push --------------------------------------------------------
say "Pushing files ..."
git init -q
git add -A
git commit -q -m "Add auto-updating profile card" || true
git branch -M main
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/$REPO.git"
else
  git remote add origin "https://github.com/$REPO.git"
fi
git push -u origin main --force
ok "Files pushed."

# --- 5. trigger + watch the workflow ----------------------------------------
say "Triggering the stats workflow ..."
sleep 3
gh workflow run "Update profile SVGs" --repo "$REPO" >/dev/null 2>&1 || \
  ok "Push already started a run (that's fine)."

sleep 5
say "Watching the latest run (Ctrl-C to stop watching; it keeps running on GitHub) ..."
RUN_ID="$(gh run list --repo "$REPO" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)"
if [ -n "${RUN_ID:-}" ]; then
  gh run watch "$RUN_ID" --repo "$REPO" --exit-status || \
    say "If it failed on auth, regenerate the token with repo + read:user scopes and re-run."
fi

# --- done --------------------------------------------------------------------
say "All set."
ok "Your profile: https://github.com/$USERNAME"
echo "   It refreshes automatically twice a day. Edit the INFO block in today.py to tweak text."
