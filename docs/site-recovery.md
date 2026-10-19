# Personal and Hub recovery

Personal's API runs as the `dev1` user service `personal-api.service`.
The user manager has lingering enabled, so it starts at boot without login.
The service restarts after exit with a five-second delay. Deployments reinstall
and restart the same service; the old API cron entry is removed after startup.

```bash
systemctl --user status personal-api.service
systemctl --user status site-backups.timer site-backups.service
cat ~/site-backups/last-success.json
```

The backup timer runs daily at 03:30 America/New_York, with up to two minutes
of jitter and catch-up after downtime. It includes Personal's `personal-data`,
Hub's `media`, `site/data`, `.env`, and the latest completed MySQL dump from
the existing 03:00 job. Logs, temporary files and disposable browser profiles
are excluded. It refuses missing sources or database dumps older than 36 hours.

Backups are AES256 GPG-encrypted before upload to a dedicated private Google
Drive folder. Full decryption/archive validation occurs before upload; the
uploaded size and MD5 must match before rotation. Keep the newest successful
backup from each of 14 UTC days, plus the two newest local encrypted archives.
Earlier history accumulates over time; a new installation has one restore point.
The older database-only backup job remains separate and unchanged.

The folder ID and passphrase are stored in `~/.config/personal-ops/` on the
server, with private permissions. A separate recovery-key copy is saved on the
operator's Mac at `~/.config/personal-ops/backup-passphrase-217.216.82.144`.
Keep that key in a secure password manager or another protected location: it is
required if the server is lost. Never commit it to Git or upload it with backups.

To inspect a downloaded archive without changing production:

```bash
gpg --batch --pinentry-mode loopback \
  --passphrase-file /path/to/recovery-key --decrypt backup.tar.gz.gpg |
  tar -tzf -
```

For recovery, decrypt/extract into an empty private staging directory first,
verify the files, and then plan the database/file restoration. Do not extract
over running production data. Archives are live file backups and include the
latest nightly SQL dump; files and SQL are not a single transactional snapshot.
