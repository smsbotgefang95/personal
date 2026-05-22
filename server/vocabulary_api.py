#!/usr/bin/env python3
"""Small same-origin API for shared personal site data."""

import json
import os
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_PAYLOAD = {"labels": {}, "meanings": {}, "updatedAt": None}
DEFAULT_LIFE_EVENTS_PAYLOAD = {"events": [], "updatedAt": None}


def env_path(name, default):
    return Path(os.environ.get(name, default)).expanduser()


DATA_PATH = env_path("VOCAB_DATA_PATH", "~/personal-data/vocabulary-overrides.json")
PUBLIC_PATH = os.environ.get("VOCAB_PUBLIC_PATH")
PUBLIC_PATH = Path(PUBLIC_PATH).expanduser() if PUBLIC_PATH else None
REPO_DIR = env_path("VOCAB_REPO_DIR", "~/personal")
REPO_DATA_PATH = REPO_DIR / "data" / "vocabulary-overrides.json"
ADMIN_KEY = os.environ.get("VOCAB_ADMIN_KEY", "")
GIT_SYNC = os.environ.get("VOCAB_GIT_SYNC", "1") != "0"
LIFE_EVENTS_DATA_PATH = env_path("LIFE_EVENTS_DATA_PATH", "~/personal-data/life-events.json")
LIFE_EVENTS_PUBLIC_PATH = os.environ.get("LIFE_EVENTS_PUBLIC_PATH")
LIFE_EVENTS_PUBLIC_PATH = Path(LIFE_EVENTS_PUBLIC_PATH).expanduser() if LIFE_EVENTS_PUBLIC_PATH else None
LIFE_EVENTS_REPO_DATA_PATH = REPO_DIR / "data" / "life-events.json"
LIFE_EVENTS_ADMIN_KEY = os.environ.get("LIFE_EVENTS_ADMIN_KEY", ADMIN_KEY)


def clean_map(value):
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            continue
        key = key.strip().lower()
        item = item.strip()
        if key and item:
            cleaned[key] = item[:240]
    return cleaned


def load_payload():
    try:
        with DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        payload = DEFAULT_PAYLOAD.copy()
    return {
        "labels": clean_map(payload.get("labels")),
        "meanings": clean_map(payload.get("meanings")),
        "updatedAt": payload.get("updatedAt"),
    }


def fallback_event_title(event):
    title = " ".join(part for part in (event.get("date"), event.get("area")) if part)
    if event.get("sourceColumn"):
        title = f"{title} - {event['sourceColumn']}" if title else event["sourceColumn"]
    return title


def clean_event(value):
    if not isinstance(value, dict):
        return None
    event = {}
    limits = {
        "id": 120,
        "date": 32,
        "area": 80,
        "sourceColumn": 120,
        "title": 240,
        "notes": 5000,
        "energy": 40,
        "pattern": 80,
        "people": 800,
        "tags": 800,
        "lesson": 2000,
        "action": 1000,
    }
    for key, limit in limits.items():
        item = value.get(key, "")
        if item is None:
            item = ""
        if not isinstance(item, str):
            item = str(item)
        event[key] = item.strip()[:limit]
    for key in ("impact", "importance"):
        try:
            event[key] = int(value.get(key, 0))
        except (TypeError, ValueError):
            event[key] = 0
    if not event["title"]:
        event["title"] = fallback_event_title(event)[:limits["title"]]
    if not event["id"] or not event["date"]:
        return None
    return event


def clean_life_events_payload(value):
    if not isinstance(value, dict):
        value = {}
    incoming_events = value.get("events", [])
    if not isinstance(incoming_events, list):
        incoming_events = []
    events = []
    seen = set()
    for item in incoming_events[:1500]:
        event = clean_event(item)
        if not event or event["id"] in seen:
            continue
        seen.add(event["id"])
        events.append(event)
    return {
        "events": events,
        "updatedAt": value.get("updatedAt"),
    }


def load_life_events_payload():
    try:
        with LIFE_EVENTS_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        payload = DEFAULT_LIFE_EVENTS_PAYLOAD.copy()
    return clean_life_events_payload(payload)


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def run_git(args):
    return subprocess.run(
        ["git", *args],
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        timeout=30,
    )


def sync_to_git(payload):
    if not GIT_SYNC or not (REPO_DIR / ".git").exists():
        return {"status": "skipped"}
    try:
        atomic_write(REPO_DATA_PATH, payload)
        add = run_git(["add", "data/vocabulary-overrides.json"])
        if add.returncode != 0:
            return {"status": "failed", "error": add.stderr.strip() or add.stdout.strip()}
        diff = run_git(["diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            return {"status": "unchanged"}
        commit = run_git([
            "-c", "user.name=Personal Vocabulary Bot",
            "-c", "user.email=vocabulary-bot@personal.homehomehooray.com",
            "commit", "-m", "Update citizenship vocabulary overrides",
        ])
        if commit.returncode != 0:
            return {"status": "failed", "error": commit.stderr.strip() or commit.stdout.strip()}
        push = run_git(["push", "origin", "HEAD:main"])
        if push.returncode != 0:
            return {"status": "failed", "error": push.stderr.strip() or push.stdout.strip()}
        return {"status": "pushed"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def sync_life_events_to_git(payload):
    if not GIT_SYNC or not (REPO_DIR / ".git").exists():
        return {"status": "skipped"}
    try:
        atomic_write(LIFE_EVENTS_REPO_DATA_PATH, payload)
        add = run_git(["add", "data/life-events.json"])
        if add.returncode != 0:
            return {"status": "failed", "error": add.stderr.strip() or add.stdout.strip()}
        diff = run_git(["diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            return {"status": "unchanged"}
        commit = run_git([
            "-c", "user.name=Personal Life Events Bot",
            "-c", "user.email=life-events-bot@personal.homehomehooray.com",
            "commit", "-m", "Update life events data",
        ])
        if commit.returncode != 0:
            return {"status": "failed", "error": commit.stderr.strip() or commit.stdout.strip()}
        push = run_git(["push", "origin", "HEAD:main"])
        if push.returncode != 0:
            return {"status": "failed", "error": push.stderr.strip() or push.stdout.strip()}
        return {"status": "pushed"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def write_all(payload):
    atomic_write(DATA_PATH, payload)
    if PUBLIC_PATH:
        atomic_write(PUBLIC_PATH, payload)
    git_result = sync_to_git(payload)
    if PUBLIC_PATH:
        atomic_write(PUBLIC_PATH, payload)
    return git_result


def write_life_events(payload):
    atomic_write(LIFE_EVENTS_DATA_PATH, payload)
    if LIFE_EVENTS_PUBLIC_PATH:
        atomic_write(LIFE_EVENTS_PUBLIC_PATH, payload)
    git_result = sync_life_events_to_git(payload)
    if LIFE_EVENTS_PUBLIC_PATH:
        atomic_write(LIFE_EVENTS_PUBLIC_PATH, payload)
    return git_result


class Handler(BaseHTTPRequestHandler):
    server_version = "VocabularyAPI/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/life-events":
            self.send_json(200, load_life_events_payload())
            return
        if path != "/api/vocabulary-overrides":
            self.send_error(404)
            return
        self.send_json(200, load_payload())

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/life-events":
            if LIFE_EVENTS_ADMIN_KEY and self.headers.get("X-Life-Events-Admin-Key") != LIFE_EVENTS_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(min(length, 1024 * 1024 * 2))
                incoming = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, {"ok": False, "error": "invalid_json"})
                return
            payload = clean_life_events_payload(incoming)
            payload["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            git_result = write_life_events(payload)
            self.send_json(200, {"ok": True, "payload": payload, "git": git_result})
            return
        if path != "/api/vocabulary-overrides":
            self.send_error(404)
            return
        if ADMIN_KEY and self.headers.get("X-Vocab-Admin-Key") != ADMIN_KEY:
            self.send_json(401, {"ok": False, "error": "admin_key_required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 1024 * 128))
            incoming = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"ok": False, "error": "invalid_json"})
            return
        payload = {
            "labels": clean_map(incoming.get("labels")),
            "meanings": clean_map(incoming.get("meanings")),
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        git_result = write_all(payload)
        self.send_json(200, {"ok": True, "payload": payload, "git": git_result})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


def main():
    host = os.environ.get("VOCAB_API_HOST", "127.0.0.1")
    port = int(os.environ.get("VOCAB_API_PORT", "8016"))
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        write_all(DEFAULT_PAYLOAD.copy())
    LIFE_EVENTS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LIFE_EVENTS_DATA_PATH.exists():
        write_life_events(DEFAULT_LIFE_EVENTS_PAYLOAD.copy())
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Vocabulary API listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
