#!/usr/bin/env python3
import importlib.util
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("personal_api", ROOT / "server" / "vocabulary_api.py")
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        API.URINE_LOG_DATA_PATH = Path(tmp) / "urine-log.json"
        API.write_urine_log(API.DEFAULT_URINE_LOG_PAYLOAD.copy())
        now = datetime(2026, 9, 24, 21, 15, tzinfo=timezone.utc)
        status, response = API.add_urine_entry({"volumeMl": 250, "source": "siri"}, now=now)
        assert status == 200
        assert response["entry"]["volumeMl"] == 250
        assert response["entry"]["date"] == "2026-09-24"
        assert response["entry"]["time"] == "17:15"
        assert response["entry"]["source"] == "siri"
        entry_id = response["entry"]["id"]
        status, _ = API.add_urine_entry({"id": entry_id, "volumeMl": 250, "date": "2026-09-24", "time": "17:15"}, now=now)
        assert status == 200
        assert len(API.load_urine_log_payload()["entries"]) == 1
        status, response = API.add_urine_entry({"volumeMl": 0}, now=now)
        assert status == 400
        assert response["error"] == "invalid_entry"
    print("urine log API tests passed")

if __name__ == "__main__":
    main()
