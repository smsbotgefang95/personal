#!/usr/bin/env bash
set -euo pipefail

REPO_SSH_URL="git@github.com-personal:smsbotgefang95/personal.git"
DEFAULT_TARGET="$HOME/djangoprojects/hhh_personal"
TARGET_DIR="${1:-$DEFAULT_TARGET}"
KEY_PATH="$HOME/.ssh/id_ed25519_personal_github"
SSH_CONFIG="$HOME/.ssh/config"
HOST_ALIAS="github.com-personal"

echo "Setting up GitHub SSH access for smsbotgefang95/personal"
echo

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is intended for macOS."
  exit 1
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [[ ! -f "$KEY_PATH" ]]; then
  echo "Creating SSH key: $KEY_PATH"
  ssh-keygen -t ed25519 -C "personal repo GitHub key" -f "$KEY_PATH" -N ""
else
  echo "Using existing SSH key: $KEY_PATH"
fi

chmod 600 "$KEY_PATH"
chmod 644 "$KEY_PATH.pub"

touch "$SSH_CONFIG"
chmod 600 "$SSH_CONFIG"

if ! grep -q "Host $HOST_ALIAS" "$SSH_CONFIG"; then
  cat >> "$SSH_CONFIG" <<EOF

Host $HOST_ALIAS
  HostName github.com
  User git
  IdentityFile $KEY_PATH
  IdentitiesOnly yes
  AddKeysToAgent yes
  UseKeychain yes
EOF
  echo "Added $HOST_ALIAS to $SSH_CONFIG"
else
  echo "$HOST_ALIAS already exists in $SSH_CONFIG"
fi

ssh-add --apple-use-keychain "$KEY_PATH" >/dev/null 2>&1 || ssh-add "$KEY_PATH"

echo
echo "Your GitHub public key has been copied to the clipboard:"
echo
cat "$KEY_PATH.pub"
echo
pbcopy < "$KEY_PATH.pub"

echo "Opening GitHub's SSH key page."
open "https://github.com/settings/ssh/new"
echo
echo "Paste the key into GitHub, save it, then come back here."
read -r -p "Press Enter after you added the key to GitHub..."

echo
echo "Testing GitHub SSH access..."
ssh -T "$HOST_ALIAS" || true

echo
if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "Repo already exists at $TARGET_DIR"
  git -C "$TARGET_DIR" remote set-url origin "$REPO_SSH_URL"
  git -C "$TARGET_DIR" pull --ff-only
else
  mkdir -p "$(dirname "$TARGET_DIR")"
  git clone "$REPO_SSH_URL" "$TARGET_DIR"
fi

echo
echo "Done. Repo is ready at:"
echo "$TARGET_DIR"
echo
echo "Future git pull/push commands in this repo should not ask for a GitHub password."
