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
    for value, expected in {
        "Monterey": "Moderate", "Motor": "Moderate", "Moderat": "Moderate",
        "mod erate urgency.": "Moderate", "moderaet": "Moderate",
        "Straw": "Strong", "strnog": "Strong", "Stron": "Strong",
        "Mlid": "Mild", "milld": "Mild", " MILD ": "Mild",
        "": "", "none": "none", "very strong": "very strong",
        "unknown": "unknown", "moderately": "moderately",
    }.items():
        assert API.clean_urine_urgency(value) == expected, value
    with tempfile.TemporaryDirectory() as tmp:
        API.URINE_LOG_DATA_PATH = Path(tmp) / "urine-log.json"
        API.write_urine_log(API.DEFAULT_URINE_LOG_PAYLOAD.copy())
        now = datetime(2026, 9, 24, 21, 15, tzinfo=timezone.utc)
        status, response = API.add_urine_entry({"volumeMl": 250, "source": "siri", "urgency": "Monterey"}, now=now)
        assert status == 200
        assert response["entry"]["volumeMl"] == 250
        assert response["entry"]["date"] == "2026-09-24"
        assert response["entry"]["time"] == "17:15"
        assert response["entry"]["source"] == "siri"
        assert response["entry"]["urgency"] == "Moderate"
        assert API.load_urine_log_payload()["entries"][0]["urgency"] == "Moderate"
        legacy = {**response["entry"], "urgency": "Straw"}
        API.write_urine_log({"entries": [legacy], "updatedAt": None})
        corrected = API.load_urine_log_payload()["entries"][0]
        assert corrected == {**legacy, "urgency": "Strong"}
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
