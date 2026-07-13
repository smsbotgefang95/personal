#!/usr/bin/env python3
"""Build a compact recent-task snapshot for time-analysis.html."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "time-recent-tasks.json"
SOURCE_FILES = [
    ROOT / "data" / "ClickUp Entries_W22.csv",
    ROOT / "data" / "ClickUp Entries_W18~W21.csv",
    ROOT / "data" / "⏰ Time Analysis_2026 - Entries.csv",
]
LIST_NAME_MAP = {
    "901306296518": "🌼 Survival",
    "901301650324": "🌈 Personal",
    "900601952633": "🚀 On Business",
    "901301162602": "👩🏻‍💻 In Business",
}
LIST_ID_BY_NAME = {name: list_id for list_id, name in LIST_NAME_MAP.items()}
LIST_ID_BY_NAME["🌼 Survival Mode"] = "901306296518"
RECENT_LIMIT = 240


def clean_label(value: object, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def display_list_name(value: object, fallback: str = "Uncategorized") -> str:
    text = clean_label(value, fallback)
    return "🌼 Survival" if text == "🌼 Survival Mode" else text


def task_id_for(task_name: object) -> str:
    value = clean_label(task_name, "task")
    value = re.sub(r"^[^a-z0-9]+", "", value.lower())
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "task"


def effective_task_id(task_id: object, task_name: object) -> str:
    return clean_label(task_id) or task_id_for(task_name)


def normalize_task_type(value: object) -> str:
    label = clean_label(value, "Other")
    if re.search("owner", label, re.I):
        return "Owner"
    if re.search("manager", label, re.I):
        return "Manager"
    if re.search("admin", label, re.I):
        return "Admin"
    if re.search("work", label, re.I):
        return "Work"
    return "Other" if label == "Uncategorized" else label


def normalize_task_category(value: object) -> str:
    return clean_label(value)


def normalized_task_status(value: object) -> str:
    return "done" if re.search(r"complete|done|closed", clean_label(value), re.I) else "todo"


def parse_clickup_timestamp(value: object) -> datetime | None:
    text = clean_label(value)
    if not text:
        return None
    try:
        return datetime.fromtimestamp(int(float(text)) / 1000, tz=timezone.utc)
    except ValueError:
        return None


def parse_duration_text(value: object) -> int:
    parts = [int(part) for part in clean_label(value).split(":") if part.isdigit()]
    if len(parts) != 3:
        return 0
    hours, minutes, seconds = parts
    return ((hours * 3600) + (minutes * 60) + seconds) * 1000


def synthetic_week_date(week_label: object) -> datetime | None:
    match = re.search(r"W(\d+)", clean_label(week_label), re.I)
    if not match:
        return None
    week_number = int(match.group(1))
    return datetime(2025, 12, 28, tzinfo=timezone.utc) + timedelta(days=(week_number - 1) * 7)


def parse_time_on_date(value: object, date: datetime | None) -> datetime | None:
    if date is None:
        return None
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)$", clean_label(value), re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    meridian = match.group(4).upper()
    if meridian == "PM" and hour != 12:
        hour += 12
    if meridian == "AM" and hour == 12:
        hour = 0
    return date.replace(hour=hour, minute=minute, second=second)


def iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat().replace("+00:00", "Z")


def normalize_clickup_entry(row: dict[str, str], source_file: Path, index: int) -> dict[str, object] | None:
    start = parse_clickup_timestamp(row.get("Start"))
    stop = parse_clickup_timestamp(row.get("Stop"))
    if start is None and stop is None:
        return None
    task_name = clean_label(row.get("Task Name"), "Untitled task")
    task_id = effective_task_id(row.get("Task ID"), task_name)
    list_id = clean_label(row.get("List ID"), "unknown-list")
    list_name = LIST_NAME_MAP.get(list_id, display_list_name(row.get("List Name")))
    return {
        "id": clean_label(row.get("Time Entry ID"), f"{source_file}:{index}:{task_id}"),
        "sourceFile": f"data/{source_file.name}",
        "sourceIndex": index,
        "sourceType": "clickup-recent",
        "start": iso(start),
        "stop": iso(stop),
        "updatedAt": iso(stop or start),
        "durationMs": int(float(row.get("Time Tracked") or 0)),
        "listId": list_id,
        "listName": list_name,
        "taskId": task_id,
        "taskName": task_name,
        "department": clean_label(row.get("Department")),
        "priority": clean_label(row.get("Priority")),
        "section": clean_label(row.get("Section")),
        "taskCategory": normalize_task_category(row.get("Task Category")),
        "taskType": normalize_task_type(row.get("Task Type")),
        "dueDate": "",
        "dueDateText": clean_label(row.get("Due Date Text")),
        "dueTime": "",
        "startDate": "",
        "startDateText": clean_label(row.get("Start Date Text")),
        "recurring": False,
        "recurringText": "",
        "taskOrder": clean_label(row.get("Task Order")),
        "notes": clean_label(row.get("Description")),
        "status": normalized_task_status(row.get("Task Status")),
    }


def normalize_legacy_entry(row: dict[str, str], source_file: Path, index: int) -> dict[str, object] | None:
    week_start = synthetic_week_date(row.get("Week\n#"))
    start = parse_time_on_date(row.get("Start\nTime"), week_start)
    stop = parse_time_on_date(row.get("End\nTime"), week_start)
    if start is not None and stop is not None and stop < start:
        stop += timedelta(days=1)
    if start is None and stop is None:
        return None
    list_name = display_list_name(row.get("List"))
    list_id = clean_label(row.get("List ID"), LIST_ID_BY_NAME.get(list_name, f"legacy-list:{list_name}"))
    task_name = clean_label(row.get("Task"), "Untitled task")
    task_id = effective_task_id(row.get("Task ID"), task_name)
    return {
        "id": f"legacy-recent:{source_file.name}:{index}",
        "sourceFile": f"data/{source_file.name}",
        "sourceIndex": index,
        "sourceType": "legacy-recent",
        "start": iso(start),
        "stop": iso(stop),
        "updatedAt": iso(stop or start),
        "durationMs": parse_duration_text(row.get("Duration\nText")),
        "listId": list_id,
        "listName": LIST_NAME_MAP.get(list_id, list_name),
        "taskId": task_id,
        "taskName": task_name,
        "department": clean_label(row.get("Department")),
        "priority": clean_label(row.get("Priority")),
        "section": clean_label(row.get("Section")),
        "taskCategory": normalize_task_category(row.get("Task\nCategory")),
        "taskType": normalize_task_type(row.get("Task\nType")),
        "dueDate": "",
        "dueDateText": "",
        "dueTime": "",
        "startDate": "",
        "startDateText": "",
        "recurring": False,
        "recurringText": "",
        "taskOrder": clean_label(row.get("Task Order")),
        "notes": clean_label(row.get("Notes")),
        "status": "todo",
    }


def normalize_row(row: dict[str, str], source_file: Path, index: int) -> dict[str, object] | None:
    if row.get("Time Entry ID"):
        return normalize_clickup_entry(row, source_file, index)
    if row.get("Week\n#"):
        return normalize_legacy_entry(row, source_file, index)
    return None


def recent_key(entry: dict[str, object]) -> str:
    list_id = clean_label(entry.get("listId"), "unknown-list")
    task_id = clean_label(entry.get("taskId"))
    task_name = re.sub(r"\s+", " ", clean_label(entry.get("taskName"), "Untitled task").lower()).strip()
    return f"{list_id}|||{'id:' + task_id if task_id else 'name:' + task_name}"


def completed_at(entry: dict[str, object]) -> str:
    return clean_label(entry.get("stop")) or clean_label(entry.get("updatedAt")) or clean_label(entry.get("start"))


def load_entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for source_file in SOURCE_FILES:
        with source_file.open(encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                entry = normalize_row(row, source_file, index)
                if entry:
                    entries.append(entry)
    entries.sort(key=completed_at, reverse=True)
    by_task: dict[str, dict[str, object]] = {}
    for entry in entries:
        key = recent_key(entry)
        if key not in by_task:
            by_task[key] = entry
        if len(by_task) >= RECENT_LIMIT:
            break
    return list(by_task.values())


def main() -> None:
    entries = load_entries()
    payload = {
        "version": "2026-07-13",
        "generatedAt": clean_label(entries[0].get("updatedAt")) if entries else "",
        "sourceFiles": [f"data/{path.name}" for path in SOURCE_FILES],
        "entries": entries,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} recent tasks to {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
