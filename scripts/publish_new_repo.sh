#!/usr/bin/env bash
# Created: 2026-04-18T12:20:22Z

set -o errexit
set -o nounset
set -o pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/publish_new_repo.sh <repo-name> [--public|--private]

Examples:
  ./scripts/publish_new_repo.sh ACE-RealEstate-Showcase --public
  ./scripts/publish_new_repo.sh ace-real-estate --private

Behavior:
  - Requires GitHub CLI (gh) and an authenticated session (gh auth status)
  - Creates a new GitHub repository under your authenticated account
  - Sets/updates local origin to the new repo
  - Pushes the current branch with upstream tracking
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "" ]]; then
  usage
  exit 0
fi

REPO_NAME="$1"
VISIBILITY="${2:---public}"

if [[ "$VISIBILITY" != "--public" && "$VISIBILITY" != "--private" ]]; then
  echo "Error: visibility must be --public or --private"
  usage
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI (gh) is not installed."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: gh is not authenticated. Run: gh auth login"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: current directory is not a git repository."
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ -z "$CURRENT_BRANCH" ]]; then
  echo "Error: could not determine current branch."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Warning: You have uncommitted changes."
  echo "Please commit before publishing to ensure a clean first push."
  exit 1
fi

OWNER="$(gh api user --jq .login)"
REMOTE_URL="https://github.com/${OWNER}/${REPO_NAME}.git"

echo "Creating GitHub repo: ${OWNER}/${REPO_NAME} (${VISIBILITY#--})"
gh repo create "${OWNER}/${REPO_NAME}" "$VISIBILITY" --source=. --remote=origin --push=false

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

echo "Pushing branch '${CURRENT_BRANCH}' to origin..."
git push -u origin "$CURRENT_BRANCH"

echo "Done."
echo "Repo URL: https://github.com/${OWNER}/${REPO_NAME}"
