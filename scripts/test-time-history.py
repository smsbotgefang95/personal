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
            manual = {**entries[0], "id": "manual-first", "taskId": "sleep", "taskName": "Sleep"}
            first = request({**recovery, "entries": [manual]})["payload"]
            retry = request({**first, "entries": [{**manual, "id": "manual-retry"}]})["payload"]
            assert sum(e["id"].startswith("manual-") for e in retry["entries"]) == 1, "a retry with a fresh ID must not count a manual interval twice"
            assert retry["activeEntry"] == first["activeEntry"], "manual logging must preserve the running timer"
            edit = {**manual, "stop": "2026-06-04T12:02:00Z", "durationMs": 120000, "updatedAt": "2026-10-28T11:00:00Z"}
            edited = request({**retry, "entries": [edit]})["payload"]
            assert next(e for e in edited["entries"] if e["id"] == manual["id"])["durationMs"] == 120000, "manual interval deduplication must allow existing entries to be edited"
            # Incremental saves return one interval, retaining history and the
            # latest server timer/metadata even when the client is stale.
            before = request()
            before["taskOverrides"] = {"personal|||unrelated": {"status": "done", "notes": "preserve"}}
            request(before)
            before = request()
            added = {**manual, "id": "manual-small", "taskId": "small", "taskName": "Small save"}
            delta = {"appendEntriesOnly": True, "entries": [added],
                     "activeEntry": None, "deletedEntryKeys": ["id:history-2"],
                     "taskOverrides": {"personal|||small": {"status": "done", "updatedAt": "2026-10-29T16:00:00Z"}}}
            compact = request(delta)
            assert compact["partialEntries"] is True
            assert len(compact["payload"]["entries"]) == 1, "incremental response must not return old history"
            assert len(json.dumps(compact)) < 5000, "response should stay small with thousands of historical entries"
            after = request()
            assert len(after["entries"]) == len(before["entries"]) + 1
            assert after["activeEntry"] == before["activeEntry"], "append must preserve the server timer"
            assert after["deletedEntryKeys"] == before["deletedEntryKeys"]
            assert after["taskMerges"] == before["taskMerges"]
            assert after["taskOverrides"]["personal|||unrelated"] == before["taskOverrides"]["personal|||unrelated"]
            assert after["taskOverrides"]["personal|||small"]["status"] == "done"
            repeated = request({**delta, "entries": [{**added, "id": "manual-small-retry"}]})
            assert repeated["payload"]["entries"][0]["id"] == "manual-small", "retry must return the canonical saved ID"
            assert len(request()["entries"]) == len(after["entries"]), "append retry must not duplicate the interval"
            changed = {**added, "stop": "2026-06-04T12:03:00Z", "durationMs": 180000,
                       "updatedAt": "2026-10-29T17:00:00Z"}
            edit_response = request({"appendEntriesOnly": True, "entries": [changed]})
            assert len(edit_response["payload"]["entries"]) == 1
            assert edit_response["payload"]["entries"][0]["durationMs"] == 180000
            stored = request()
            assert len(stored["entries"]) == len(after["entries"]), "incremental edit must replace the existing entry"
            assert stored["activeEntry"] == after["activeEntry"], "editing must preserve the current server timer"
            assert stored["taskOverrides"] == after["taskOverrides"]
            stale_edit = request({"appendEntriesOnly": True, "entries": [added]})
            assert stale_edit["payload"]["entries"][0]["durationMs"] == 180000, "stale retry must return the newer server entry"
            request({"appendEntriesOnly": True, "entries": [], "taskOverrides": {
                "personal|||small": {"status": "todo", "updatedAt": "2026-01-01T00:00:00Z"}}})
            assert request()["taskOverrides"]["personal|||small"]["status"] == "done", "stale append must preserve newer task updates"
        finally:
            server.shutdown()
            server.server_close()
    print("Time history HTTP retention, stale-save, edit, and deletion checks passed.")


if __name__ == "__main__":
    run()
