#!/bin/bash
set -euo pipefail
loginctl enable-linger "$(id -un)"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/personal-api.service" <<'UNIT'
[Unit]
Description=Personal website data API
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/bin/bash %h/personal/scripts/run-personal-api.sh
Restart=always
RestartSec=5
TimeoutStopSec=30
UMask=0077
StandardOutput=append:%h/personal-data/vocabulary-api.log
StandardError=inherit

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
# Retire only the old deployment's unmanaged process, never an unrelated PID.
if ! systemctl --user is-active --quiet personal-api.service; then
    /usr/bin/python3 - <<'PY'
import os, signal, time
from pathlib import Path
p = Path.home() / 'personal-data/vocabulary-api.pid'
if p.exists():
    pid = int(p.read_text().strip())
    cmd = Path(f'/proc/{pid}/cmdline')
    expected = str(Path.home() / 'personal/server/vocabulary_api.py').encode()
    if cmd.exists() and expected in cmd.read_bytes().split(b'\0'):
        os.kill(pid, signal.SIGTERM)
        for _ in range(100):
            if not cmd.exists():
                break
            time.sleep(0.1)
        else:
            raise SystemExit('Previous API did not stop; refusing a second process')
PY
fi
systemctl --user enable personal-api.service
systemctl --user restart personal-api.service
sleep 2
systemctl --user is-active --quiet personal-api.service
# Remove the legacy boot entry only after the service starts successfully.
CRON_TMP=$(mktemp)
trap 'rm -f "$CRON_TMP"' EXIT
crontab -l 2>/dev/null | grep -vF '# personal-vocabulary-api-reboot' > "$CRON_TMP" || true
crontab "$CRON_TMP"
