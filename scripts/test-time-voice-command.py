#!/usr/bin/env python3

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vocabulary_api", ROOT / "server" / "vocabulary_api.py")
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def run():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        API.TIME_ENTRIES_DATA_PATH = temp / "time-entries.json"
        API.TIME_TASK_CATALOG_PATH = temp / "time-task-catalog.json"
        catalog = {
            "entries": [
                {"listId": "business", "listName": "In Business", "taskId": "books", "taskName": "💳 Reconcile books", "department": "Finance"},
                {"listId": "personal", "listName": "Personal", "taskId": "walk", "taskName": "🚶 Walk"},
                {"listId": "business", "listName": "In Business", "taskId": "vendor-calls", "taskName": "Call vendors"},
                {"listId": "business", "listName": "In Business", "taskId": "seller-calls", "taskName": "Call sellers"},
            ]
        }
        API.TIME_TASK_CATALOG_PATH.write_text(json.dumps(catalog), encoding="utf-8")
        API.TIME_ENTRIES_DATA_PATH.write_text(json.dumps(API.DEFAULT_TIME_ENTRIES_PAYLOAD), encoding="utf-8")

        status, response = API.apply_time_voice_command({"action": "switch", "task": "reconcile books"}, "2026-09-24T12:00:00.000Z")
        assert_equal(status, 200, "exact match status")
        assert_equal(response["activeTask"], "💳 Reconcile books", "exact match task")

        status, response = API.apply_time_voice_command({"action": "switch", "task": "walk"}, "2026-09-24T12:15:00.000Z")
        assert_equal(status, 200, "partial match status")
        payload = API.load_time_entries_payload()
        assert_equal(payload["activeEntry"]["taskName"], "🚶 Walk", "new active task")
        assert_equal(payload["entries"][0]["taskName"], "💳 Reconcile books", "previous task saved")
        assert_equal(payload["entries"][0]["durationMs"], 900000, "previous duration")

        status, response = API.apply_time_voice_command({"action": "switch", "task": "call"}, "2026-09-24T12:20:00.000Z")
        assert_equal(status, 409, "ambiguous match status")
        assert_equal(response["error"], "ambiguous_task", "ambiguous match error")

        status, response = API.apply_time_voice_command({"action": "stop"}, "2026-09-24T12:30:00.000Z")
        assert_equal(status, 200, "stop status")
        assert_equal(API.load_time_entries_payload()["activeEntry"], None, "timer stopped")

        status, response = API.apply_time_voice_command({"action": "switch", "task": "does not exist"}, "2026-09-24T12:35:00.000Z")
        assert_equal(status, 404, "missing task status")
        assert_equal(response["message"], "I could not find that task. Try saying more of its name.", "missing task response")

    print("time voice command tests passed")


if __name__ == "__main__":
    run()
