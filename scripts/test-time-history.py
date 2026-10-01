#!/usr/bin/env python3
"""Exercise history retention through the real HTTP save and load routes."""
import importlib.util
import json
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vocabulary_api", ROOT / "server/vocabulary_api.py")
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)


def run():
    with tempfile.TemporaryDirectory() as directory:
        API.TIME_ENTRIES_DATA_PATH = Path(directory) / "time-entries.json"
        API.TIME_ENTRIES_ADMIN_KEY = "test-history-key"
        server = ThreadingHTTPServer(("127.0.0.1", 0), API.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/api/time-entries"

        def request(payload=None):
            data = None if payload is None else json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json", "X-Time-Tracking-Admin-Key": "test-history-key"
            })
            with urllib.request.urlopen(req) as response:
                return json.load(response)

        try:
            entries = [{
                "id": f"history-{index}", "start": "2026-06-04T12:00:00Z",
                "stop": "2026-06-04T12:01:00Z", "durationMs": 60000,
                "taskName": "Historical task", "listId": "personal",
                "updatedAt": "2026-06-04T12:01:00Z"
            } for index in range(6001)]
            saved = request({"entries": entries})["payload"]
            assert len(saved["entries"]) == 6001, "save must retain more than 5000 entries"
            assert len(request()["entries"]) == 6001, "load must retain full history"
            edited = {**entries[0], "taskName": "Corrected task", "updatedAt": "2026-10-01T12:00:00Z"}
            request({"entries": [edited], "deletedEntryKeys": ["id:history-1"]})
            stale = request({"entries": entries[:2]})["payload"]
            by_id = {entry["id"]: entry for entry in stale["entries"]}
            assert len(by_id) == 6000, "stale save must preserve missing history"
            assert "history-1" not in by_id, "stale save must not resurrect a deleted entry"
            assert by_id["history-0"]["taskName"] == "Corrected task", "stale edit must not replace a newer edit"
            assert len(json.loads(API.TIME_ENTRIES_DATA_PATH.read_text())["entries"]) == 6000
            active = {**entries[0], "id": "running", "stop": "", "durationMs": 0}
            request({**stale, "activeEntry": active, "taskOverrides": {}})
            before = request()
            recovery = request({"restoreMissingHistory": True, "entries": [
                {**entries[0], "id": "recovered"},
                {**edited, "taskName": "Obsolete backup edit", "updatedAt": "2027-01-01T00:00:00Z"},
                entries[1],
            ]})["payload"]
            assert recovery["activeEntry"] == before["activeEntry"], "recovery must preserve the live timer"
            assert recovery["taskOverrides"] == before["taskOverrides"]
            restored = {entry["id"]: entry for entry in recovery["entries"]}
            assert restored["history-0"] == by_id["history-0"], "recovery must preserve current edits"
            assert "history-1" not in restored, "recovery must honor explicit deletions"
            assert "recovered" in restored
        finally:
            server.shutdown()
            server.server_close()
    print("Time history HTTP retention, stale-save, edit, and deletion checks passed.")


if __name__ == "__main__":
    run()
