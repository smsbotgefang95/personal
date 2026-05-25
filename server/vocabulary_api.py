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
DEFAULT_LIFE_EVENTS_PAYLOAD = {"events": [], "deletedImportIds": [], "updatedAt": None}
DEFAULT_TIME_ENTRIES_PAYLOAD = {"entries": [], "activeEntry": None, "taskOverrides": {}, "updatedAt": None}


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
TIME_ENTRIES_DATA_PATH = env_path("TIME_ENTRIES_DATA_PATH", "~/personal-data/time-entries.json")
TIME_ENTRIES_ADMIN_KEY = os.environ.get("TIME_ENTRIES_ADMIN_KEY", ADMIN_KEY)


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
        "endDate": 32,
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


def clean_deleted_import_ids(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    seen = set()
    for item in value[:1500]:
        item = str(item).strip()
        if not item.startswith("sheet-import-"):
            continue
        suffix = item.removeprefix("sheet-import-")
        if not suffix.isdigit() or item in seen:
            continue
        seen.add(item)
        cleaned.append(item[:120])
    return cleaned


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
        "deletedImportIds": clean_deleted_import_ids(value.get("deletedImportIds")),
        "updatedAt": value.get("updatedAt"),
    }


def load_life_events_payload():
    try:
        with LIFE_EVENTS_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        payload = DEFAULT_LIFE_EVENTS_PAYLOAD.copy()
    return clean_life_events_payload(payload)


def clean_time_text(value, limit=240):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def clean_time_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def clean_due_date(value):
    value = clean_time_text(value, 10)
    if not value:
        return ""
    parts = value.split("-")
    if len(parts) != 3:
        return ""
    year, month, day = parts
    if len(year) != 4 or len(month) != 2 or len(day) != 2:
        return ""
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return ""
    if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
        return ""
    return value


def clean_recurrence(value):
    value = clean_time_text(value, 20).lower()
    return value if value in {"none", "daily", "weekly", "monthly", "custom"} else "none"


def clean_task_overrides(value):
    if not isinstance(value, dict):
        return {}
    overrides = {}
    for key, item in list(value.items())[:5000]:
        key = clean_time_text(key, 260)
        if "|||" not in key or not isinstance(item, dict):
            continue
        recurrence = clean_recurrence(item.get("recurrence"))
        override = {
            "dueDate": clean_due_date(item.get("dueDate")),
            "status": "done" if item.get("status") == "done" else "todo",
            "recurrence": recurrence,
            "recurringText": clean_time_text(item.get("recurringText"), 120) if recurrence == "custom" else "",
            "taskOrder": clean_time_text(item.get("taskOrder"), 80),
            "updatedAt": clean_time_text(item.get("updatedAt"), 40),
        }
        if (
            override["dueDate"]
            or override["status"] == "done"
            or override["recurrence"] != "none"
            or override["recurringText"]
            or override["taskOrder"]
        ):
            overrides[key] = override
        elif item.get("dueDate") == "" or item.get("taskOrder") == "":
            overrides[key] = override
    return overrides


def clean_time_entry(value, require_stop=False):
    if not isinstance(value, dict):
        return None
    entry = {
        "id": clean_time_text(value.get("id"), 120),
        "sourceType": "native",
        "start": clean_time_text(value.get("start"), 40),
        "stop": clean_time_text(value.get("stop"), 40),
        "durationMs": clean_time_int(value.get("durationMs")),
        "listId": clean_time_text(value.get("listId"), 80),
        "listName": clean_time_text(value.get("listName"), 120),
        "taskId": clean_time_text(value.get("taskId"), 160),
        "taskName": clean_time_text(value.get("taskName"), 240),
        "department": clean_time_text(value.get("department"), 160),
        "priority": clean_time_text(value.get("priority"), 80),
        "section": clean_time_text(value.get("section"), 160),
        "taskCategory": clean_time_text(value.get("taskCategory"), 160),
        "taskType": clean_time_text(value.get("taskType"), 80),
        "dueDate": clean_time_text(value.get("dueDate"), 40),
        "dueDateText": clean_time_text(value.get("dueDateText"), 80),
        "startDate": clean_time_text(value.get("startDate"), 40),
        "startDateText": clean_time_text(value.get("startDateText"), 80),
        "recurring": bool(value.get("recurring")),
        "recurringText": clean_time_text(value.get("recurringText"), 120),
        "taskOrder": clean_time_text(value.get("taskOrder"), 80),
        "notes": clean_time_text(value.get("notes"), 4000),
        "createdAt": clean_time_text(value.get("createdAt"), 40),
        "updatedAt": clean_time_text(value.get("updatedAt"), 40),
    }
    if not entry["id"] or not entry["start"] or not entry["taskName"] or not entry["listId"]:
        return None
    if require_stop and (not entry["stop"] or entry["durationMs"] <= 0):
        return None
    if not entry["listName"]:
        entry["listName"] = entry["listId"]
    if not entry["taskId"]:
        entry["taskId"] = entry["id"]
    return entry


def clean_time_entries_payload(value):
    if not isinstance(value, dict):
        value = {}
    incoming_entries = value.get("entries", [])
    if not isinstance(incoming_entries, list):
        incoming_entries = []
    entries = []
    seen = set()
    for item in incoming_entries[:5000]:
        entry = clean_time_entry(item, require_stop=True)
        if not entry or entry["id"] in seen:
            continue
        seen.add(entry["id"])
        entries.append(entry)
    active_entry = clean_time_entry(value.get("activeEntry"), require_stop=False)
    if active_entry:
        active_entry["stop"] = ""
        active_entry["durationMs"] = 0
    return {
        "entries": entries,
        "activeEntry": active_entry,
        "taskOverrides": clean_task_overrides(value.get("taskOverrides")),
        "updatedAt": value.get("updatedAt"),
    }


def load_time_entries_payload():
    try:
        with TIME_ENTRIES_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        payload = DEFAULT_TIME_ENTRIES_PAYLOAD.copy()
    return clean_time_entries_payload(payload)


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


def write_time_entries(payload):
    atomic_write(TIME_ENTRIES_DATA_PATH, payload)
    return {"status": "stored"}


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
        if path == "/api/time-entries":
            if TIME_ENTRIES_ADMIN_KEY and self.headers.get("X-Time-Tracking-Admin-Key") != TIME_ENTRIES_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            self.send_json(200, load_time_entries_payload())
            return
        if path == "/api/life-events":
            self.send_json(200, load_life_events_payload())
            return
        if path != "/api/vocabulary-overrides":
            self.send_error(404)
            return
        self.send_json(200, load_payload())

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/time-entries":
            if TIME_ENTRIES_ADMIN_KEY and self.headers.get("X-Time-Tracking-Admin-Key") != TIME_ENTRIES_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(min(length, 1024 * 1024 * 4))
                incoming = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, {"ok": False, "error": "invalid_json"})
                return
            payload = clean_time_entries_payload(incoming)
            payload["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_result = write_time_entries(payload)
            self.send_json(200, {"ok": True, "payload": payload, "git": write_result})
            return
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
    TIME_ENTRIES_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TIME_ENTRIES_DATA_PATH.exists():
        write_time_entries(DEFAULT_TIME_ENTRIES_PAYLOAD.copy())
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Vocabulary API listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
