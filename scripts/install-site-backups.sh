#!/bin/bash
set -euo pipefail
test -s "$HOME/.config/personal-ops/backup.json"
test -s "$HOME/.config/personal-ops/backup-passphrase"
loginctl enable-linger "$(id -un)"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/site-backups.service" <<'UNIT'
[Unit]
Description=Encrypted off-server recovery backup for Personal and Hub

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 %h/personal/scripts/backup-site-data.py
UMask=0077
Nice=10
IOSchedulingClass=idle
TimeoutStartSec=6h
UNIT
cat > "$HOME/.config/systemd/user/site-backups.timer" <<'UNIT'
[Unit]
Description=Daily site backup at 03:30 America/New_York

[Timer]
OnCalendar=*-*-* 03:30:00 America/New_York
Persistent=true
RandomizedDelaySec=120
Unit=site-backups.service

[Install]
WantedBy=timers.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now site-backups.timer
