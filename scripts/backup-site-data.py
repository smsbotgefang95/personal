#!/usr/bin/env python3
"""Encrypted, verified, rotating off-server backups; no application writes."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HOME = Path.home()
OPS = HOME / '.config/personal-ops'
STATE = HOME / 'site-backups'
PREFIX = 'hhh-sites-'


def run(args):
    return subprocess.check_output(args, text=True, timeout=7200).strip()


def digest(path, algorithm):
    h = hashlib.new(algorithm)
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_backup_listing(listing):
    records = []
    pattern = re.compile(r'hhh-sites-\d{8}T\d{6}Z\.tar\.gz\.gpg')
    for row in listing.splitlines():
        parts = [part.strip() for part in row.split('|')]
        if len(parts) >= 2 and pattern.fullmatch(parts[1]):
            records.append((parts[1], parts[0]))
    return sorted(records, reverse=True)


def retained_daily_ids(records, count):
    keep, dates = set(), set()
    for name, file_id in sorted(records, reverse=True):
        day = name[len(PREFIX):len(PREFIX)+8]
        if day not in dates and len(dates) < count:
            dates.add(day)
            keep.add(file_id)
    return keep


def main():
    os.umask(0o077)
    STATE.mkdir(mode=0o700, exist_ok=True)
    lock = (STATE / 'backup.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = json.loads((OPS / 'backup.json').read_text())
    folder = config['drive_folder_id']
    key = OPS / 'backup-passphrase'
    if key.stat().st_mode & 0o077:
        raise RuntimeError('Recovery key permissions must be 600')
    dumps = sorted((HOME / 'mysql_backup/backup').glob('*-reicrm_db.sql'))
    if not dumps:
        raise RuntimeError('No database dump available')
    latest = dumps[-1]
    if dt.datetime.now().timestamp() - latest.stat().st_mtime > 36 * 3600:
        raise RuntimeError('Database backup is over 36 hours old')
    with latest.open('rb') as f:
        f.seek(max(0, latest.stat().st_size - 2048))
        if b'Dump completed on' not in f.read():
            raise RuntimeError('Database dump has no completion marker')
    sources = ['personal-data', 'reicrm/reicrm/media',
               'reicrm/reicrm/site/data', 'reicrm/reicrm/.env',
               str(latest.relative_to(HOME))]
    for source in sources:
        if not (HOME / source).exists():
            raise RuntimeError('Required backup source missing: ' + source)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = PREFIX + stamp + '.tar.gz.gpg'
    target = STATE / name
    partial = STATE / (name + '.partial')
    gpg = ['/usr/bin/gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
           '--no-symkey-cache', '--passphrase-file', str(key)]
    # Browser profiles, caches and logs are disposable runtime state. Business
    # documents and saved application records remain included.
    excludes = ['*.log', '*.pid', 'tmp*', 'playwright_profiles',
                '*chrome_profile*', 'camoufox_sdat_profile',
                'Cache', 'Code Cache', 'GPUCache', 'ShaderCache',
                'Singleton*', '*.sock']
    tar_args = ['/usr/bin/tar', '-czf', '-', '-C', str(HOME)]
    tar_args += ['--exclude=' + item for item in excludes]
    tar_args += sources
    try:
        with tempfile.TemporaryFile() as errors, partial.open('wb') as out:
            tar = subprocess.Popen(tar_args, stdout=subprocess.PIPE, stderr=errors)
            try:
                encrypted = subprocess.run(gpg + ['--symmetric', '--cipher-algo',
                    'AES256', '--compress-algo', 'none'], stdin=tar.stdout,
                    stdout=out, timeout=7200)
            finally:
                tar.stdout.close()
            rc = tar.wait(timeout=60)
            errors.seek(0)
            warnings = errors.read().decode(errors='replace')
            if rc or encrypted.returncode:
                raise RuntimeError(f'Archive/encryption failed ({rc}): {warnings}')
        partial.rename(target)
        # Read the entire decrypted archive before uploading; GPG verifies its
        # integrity protection, and tar validates the archive stream.
        decrypt = subprocess.Popen(gpg + ['--decrypt', str(target)], stdout=subprocess.PIPE)
        try:
            check = subprocess.run(['/usr/bin/tar', '-tzf', '-'],
                stdin=decrypt.stdout, stdout=subprocess.DEVNULL, timeout=7200)
        finally:
            decrypt.stdout.close()
        if decrypt.wait(timeout=60) or check.returncode:
            raise RuntimeError('Encrypted archive validation failed')
        file_id = run(['/usr/bin/gdrive', 'files', 'upload', '--parent', folder,
                       '--print-only-id', str(target)])
        if not re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
            raise RuntimeError('Upload did not return a valid Drive file ID')
        info = run(['/usr/bin/gdrive', 'files', 'info', '--size-in-bytes', file_id])
        md5 = digest(target, 'md5')
        if f'MD5: {md5}' not in info or f'Size: {target.stat().st_size}' not in info:
            raise RuntimeError('Uploaded size/checksum does not match')
        # Only our exact filename format within our dedicated folder is rotated.
        query = f"'{folder}' in parents and trashed = false"
        listing = run(['/usr/bin/gdrive', 'files', 'list', '--query', query,
                       '--max', '1000', '--skip-header', '--full-name',
                       '--field-separator', '|'])
        records = parse_backup_listing(listing)
        if (name, file_id) not in records:
            raise RuntimeError('New backup missing from remote listing; no pruning performed')
        # Keep 14 distinct UTC daily restore points (newest successful run/day).
        keep = retained_daily_ids(records, config['keep_days'])
        for remote_name, remote_id in records:
            if remote_id not in keep:
                run(['/usr/bin/gdrive', 'files', 'delete', remote_id])
        # Keep only two local encrypted copies; off-server retention is longer.
        for old in sorted(STATE.glob(PREFIX + '*.tar.gz.gpg'), reverse=True)[2:]:
            old.unlink()
        status = {'completed_at_utc': stamp, 'file_id': file_id, 'name': name,
                  'bytes': target.stat().st_size, 'md5': md5,
                  'sha256': digest(target, 'sha256'), 'sources': sources,
                  'remote_daily_restore_points': len(keep)}
        temp = STATE / 'last-success.json.tmp'
        temp.write_text(json.dumps(status, indent=2) + '\n')
        temp.replace(STATE / 'last-success.json')
        print(json.dumps(status), flush=True)
    finally:
        partial.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
