#!/usr/bin/env python3
"""Build generated Learning English dictionary data from Word by Word index text."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "word-by-word-index-raw.txt"
JSON_PATH = ROOT / "data" / "learning-dictionary-full.json"
JS_PATH = ROOT / "data" / "learning-dictionary-full.js"
REPORT_PATH = ROOT / "data" / "learning-dictionary-full-report.json"
NON_COMPOUND_PHRASES = {"get up", "go shopping"}

REF_TOKEN = r"\d{1,3}(?:-[A-Za-z0-9]{1,3})?(?![A-Za-z0-9-])"
REF_GROUP_RE = re.compile(rf"(?<=\s)({REF_TOKEN}(?:\s*,\s*(?:{REF_TOKEN}|[A-Za-z0-9]+))*)")
REF_ONLY_RE = re.compile(rf"^{REF_TOKEN}(?:\s*,\s*(?:{REF_TOKEN}|[A-Za-z0-9]+))*$")
TRAILING_REF_COMMA_RE = re.compile(rf"{REF_TOKEN},\s*$")
PAGE_HEADER_RE = re.compile(r"^(?:Page|P:)\s*\d+\s*$", re.IGNORECASE)
INDEX_INTRO_RE = re.compile(r"^.*?(?=3-point turn\s+130-25)", re.IGNORECASE | re.DOTALL)

MANUAL_WRAPPED_ENTRIES = [
    ("airplane", ["132-23"]),
    ("arrival and departure board", ["124-13"]),
    ("arrival and departure monitor", ["131-5"]),
    ("ask about the benefits", ["118-K"]),
    ("ask you some questions about your health", ["92-E"]),
    ("administrative assistant", ["119-22"]),
    ("antiseptic cleansing wipe", ["90-4"]),
    ("baggage claim area", ["131-15", "161-2"]),
    ("baggage claim check", ["131-21", "161-12"]),
    ("baggage compartment", ["124-10"]),
    ("appliance repairperson", ["30-E"]),
    ("balance the checkbook", ["81-16"]),
    ("bacon, lettuce, and tomato sandwich", ["61-27"]),
    ("bottle-return machine", ["55-25"]),
    ("bread-and-butter plate", ["63-24"]),
    ("bring in your homework", ["6-22"]),
    ("bird watching", ["135-N"]),
    ("Can you please repeat that?", ["13-21"]),
    ("Can you please say that again?", ["13-21"]),
    ("Can you please send someone to get my bags?", ["162-f"]),
    ("Do you speak..?", ["165-21"]),
    ("Don't move!", ["165-20"]),
    ("Excuse me.", ["13-16"]),
    ("Fine, thanks.", ["12-6"]),
    ("Fine.", ["12-6"]),
    ("Fire!", ["165-18"]),
    ("Freeze!", ["165-20"]),
    ("Get away from me!", ["165-17"]),
    ("Good afternoon.", ["12-3"]),
    ("Good evening.", ["12-4"]),
    ("Good morning.", ["12-2"]),
    ("Good night.", ["12-10"]),
    ("Good-bye.", ["12-9"]),
    ("Hello.", ["12-1"]),
    ("Hello. My name is...", ["13-12"]),
    ("Hello. This is... May I please speak to..?", ["13-22"]),
    ("Help!", ["165-15"]),
    ("Hi.", ["12-1"]),
    ("Hi. I'm...", ["13-12"]),
    ("How are you doing?", ["12-5"]),
    ("How are you?", ["12-5"]),
    ("I don't understand.", ["13-20"]),
    ("I like your city very much.", ["164-14"]),
    ("I'd like a wake-up call at...", ["162-d"]),
    ("I'd like to get tickets for a show.", ["162-e"]),
    ("I'd like to introduce...", ["13-15"]),
    ("I'd like to order...", ["162-a"]),
    ("I'm checking out.", ["162-f"]),
    ("I'm from...", ["164-11"]),
    ("I'm here for five days.", ["164-12"]),
    ("I'm sorry... isn't here right now.", ["13-24"]),
    ("I'm sorry. What did you say?", ["165-26"]),
    ("It's very...", ["164-14"]),
    ("I've seen... and...", ["164-13"]),
    ("Look out!", ["165-19"]),
    ("May I ask a question?", ["13-17"]),
    ("Nice to meet you, too.", ["13-14"]),
    ("Nice to meet you.", ["13-13"]),
    ("Not much.", ["12-8"]),
    ("Not too much.", ["12-8"]),
    ("Okay.", ["12-6"]),
    ("Please don't bother me!", ["165-17"]),
    ("Please go away!", ["165-17"]),
    ("Please repeat that.", ["165-24"]),
    ("Please speak slowly.", ["165-25"]),
    ("Please write that down for me.", ["165-22"]),
    ("Police!", ["165-16"]),
    ("See you later.", ["12-11"]),
    ("See you soon.", ["12-11"]),
    ("Sorry. I don't understand.", ["13-20"]),
    ("Stop!", ["165-20"]),
    ("Thank you.", ["13-18"]),
    ("Thanks.", ["13-18"]),
    ("This is...", ["13-15"]),
    ("We need some towels.", ["162-b"]),
    ("What do you call that in English?", ["165-23"]),
    ("What's new with you?", ["12-7"]),
    ("What's new?", ["12-7"]),
    ("Yes. Hold on a moment.", ["13-23"]),
    ("You're welcome.", ["13-19"]),
]


PAGE_TOPIC_RULES = [
    (range(1, 4), "personal", "Personal Information"),
    (range(4, 9), "daily", "The Classroom"),
    (range(9, 16), "daily", "Everyday Activities I"),
    (range(16, 20), "numbers", "Time"),
    (range(20, 36), "home", "Home"),
    (range(36, 42), "community", "Places Around Town I"),
    (range(42, 48), "describing", "People and Physical Descriptions"),
    (range(48, 65), "food", "Food"),
    (range(65, 74), "clothes", "Colors and Clothing"),
    (range(76, 80), "shopping", "Telephones and Cameras"),
    (range(80, 86), "services", "Community Services"),
    (range(86, 101), "health", "Health"),
    (range(101, 112), "school", "School, Subjects, and Activities"),
    (range(112, 124), "work", "Work"),
    (range(124, 134), "transportation", "Transportation and Travel"),
    (range(134, 151), "recreation", "Recreation and Entertainment"),
    (range(151, 160), "nature", "Nature"),
    (range(160, 163), "transportation", "Transportation and Travel"),
]

PREFIXES = ("anti", "auto", "bio", "co", "dis", "inter", "micro", "multi", "non", "over", "pre", "re", "sub", "super", "trans", "un")
SUFFIXES = ("tion", "sion", "ment", "ness", "less", "able", "ible", "ful", "er", "or", "ist", "ing", "ed", "s")
VOWEL_TEAMS = ("ai", "ay", "ea", "ee", "ie", "oa", "oe", "oo", "ou", "ow", "ue", "ew", "oi", "oy", "au", "aw")


@dataclass
class ParsedEntry:
    text: str
    refs: list[str]
    raw: str
    line: int


def clean_entry_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,;")


def parse_ref_group(value: str) -> list[str]:
    refs: list[str] = []
    current_page = ""
    for token in [part.strip() for part in value.split(",") if part.strip()]:
        if "-" in token:
            page, item = token.split("-", 1)
            if page.isdigit():
                current_page = page
            refs.append(f"{page}-{item}")
        elif current_page and re.fullmatch(r"[A-Za-z0-9]+", token):
            refs.append(f"{current_page}-{token}")
        else:
            current_page = token if token.isdigit() else current_page
            refs.append(token)
    return refs


def page_from_ref(ref: str) -> int | None:
    match = re.match(r"^(\d{1,3})", ref)
    return int(match.group(1)) if match else None


def infer_theme_topic(pages: list[int]) -> tuple[str, str]:
    for page in pages:
        for page_range, theme, topic in PAGE_TOPIC_RULES:
            if page in page_range:
                return theme, topic
    return "daily", "Everyday Conversation"


def placement_from_ref(ref: str) -> dict | None:
    page = page_from_ref(ref)
    if page is None:
        return None
    for page_range, theme, topic in PAGE_TOPIC_RULES:
        if page in page_range:
            return {"ref": ref, "page": page, "theme": theme, "topic": topic}
    return {"ref": ref, "page": page, "theme": "daily", "topic": "Everyday Conversation"}


def get_prefix(text: str) -> str:
    normalized = re.sub(r"[^a-z]", "", text.lower())
    return next((prefix for prefix in PREFIXES if normalized.startswith(prefix) and len(normalized) > len(prefix) + 2), "none")


def get_suffix(text: str) -> str:
    normalized = re.sub(r"[^a-z]", "", text.lower())
    return next((suffix for suffix in SUFFIXES if normalized.endswith(suffix) and len(normalized) > len(suffix) + 2), "none")


def get_syllable_type(text: str) -> str:
    normalized = re.sub(r"[^a-z]", "", text.lower())
    if not normalized:
        return ""
    if normalized.endswith("e") and len(normalized) > 2:
        return "silent-e"
    if any(team in normalized for team in VOWEL_TEAMS):
        return "vowel-team"
    return "closed" if re.search(r"[aeiou][^aeiou]$", normalized) else "open"


def build_entries(raw_text: str) -> tuple[list[dict], dict]:
    parsed: list[ParsedEntry] = []
    report = {
        "unparsedLines": [],
        "wrappedLines": [],
        "duplicateEntries": [],
        "suspiciousRefs": [],
        "missingIpa": [],
        "missingCategory": [],
        "missingPlacements": [],
    }
    pending_fragments: list[dict] = []
    last_entry: ParsedEntry | None = None
    continuation_entry: ParsedEntry | None = None

    for line_number, original_line in enumerate(raw_text.splitlines(), 1):
        line = clean_entry_text(original_line)
        if not line:
            continue
        if PAGE_HEADER_RE.fullmatch(line):
            continue
        line = clean_entry_text(INDEX_INTRO_RE.sub("", line))
        if not line:
            continue

        if REF_ONLY_RE.fullmatch(line):
            if continuation_entry:
                continuation_entry.refs.extend(parse_ref_group(line))
                report["wrappedLines"].append({"line": line_number, "text": line, "attachedTo": continuation_entry.text})
                continuation_entry = None
                continue
            report["unparsedLines"].append({"line": line_number, "text": original_line, "reason": "reference-only line without active continuation"})
            continue

        matches = list(REF_GROUP_RE.finditer(f" {line}"))
        if not matches:
            pending_fragments.append({"line": line_number, "text": line})
            report["wrappedLines"].append({"line": line_number, "text": line, "reason": "manual wrapped fragment"})
            continue

        shifted_line = f" {line}"
        cursor = 1
        produced = False
        for match_index, match in enumerate(matches):
            text = clean_entry_text(shifted_line[cursor:match.start()])
            refs = parse_ref_group(match.group(1))
            if not text and match.start() == cursor and match_index < len(matches) - 1:
                continue
            cursor = match.end()
            if not text:
                if last_entry:
                    last_entry.refs.extend(refs)
                    continue
                report["unparsedLines"].append({"line": line_number, "text": original_line})
                continue
            entry = ParsedEntry(text=text, refs=refs, raw=line, line=line_number)
            parsed.append(entry)
            last_entry = entry
            produced = True

        trailing = clean_entry_text(shifted_line[cursor:])
        if trailing:
            pending_fragments.append({"line": line_number, "text": trailing})
            report["wrappedLines"].append({"line": line_number, "text": trailing, "reason": "trailing text after references"})
        if not produced:
            report["unparsedLines"].append({"line": line_number, "text": original_line})
        elif TRAILING_REF_COMMA_RE.search(line):
            continuation_entry = last_entry
            report["wrappedLines"].append({"line": line_number, "text": line, "reason": "trailing comma"})
        else:
            continuation_entry = None

    for text, refs in MANUAL_WRAPPED_ENTRIES:
        parsed.append(ParsedEntry(text=text, refs=refs, raw=text, line=0))
        report["wrappedLines"].append({"line": None, "text": text, "reason": "manual reconstruction"})

    for fragment in pending_fragments:
        if not any(fragment["text"].casefold() in text.casefold() for text, _ in MANUAL_WRAPPED_ENTRIES):
            report["unparsedLines"].append({**fragment, "reason": "unmatched wrapped fragment"})

    merged: dict[str, ParsedEntry] = {}
    for entry in parsed:
        key = entry.text.casefold()
        if key not in merged:
            merged[key] = entry
            continue
        existing = merged[key]
        existing.refs.extend(ref for ref in entry.refs if ref not in existing.refs)
        report["duplicateEntries"].append({"text": entry.text, "line": entry.line, "mergedIntoLine": existing.line})

    entries = []
    for index, entry in enumerate(sorted(merged.values(), key=lambda item: item.text.casefold()), 1):
        refs = list(dict.fromkeys(entry.refs))
        pages = sorted({page for ref in refs if (page := page_from_ref(ref)) is not None})
        suspicious_refs = [ref for ref in refs if page_from_ref(ref) is None or (page_from_ref(ref) or 0) > 209]
        placements = [placement for ref in refs if (placement := placement_from_ref(ref))]
        if placements:
            theme = placements[0]["theme"]
            topic = placements[0]["topic"]
        else:
            theme, topic = infer_theme_topic(pages)
            report["missingCategory"].append(entry.text)
            report["missingPlacements"].append({"text": entry.text, "refs": refs})
        if suspicious_refs:
            report["suspiciousRefs"].append({"text": entry.text, "refs": suspicious_refs})
        normalized = entry.text.casefold()
        word = {
            "id": f"index-{index:04d}-{re.sub(r'[^a-z0-9]+', '-', normalized).strip('-') or 'entry'}",
            "type": "word",
            "text": entry.text,
            "word": entry.text,
            "chinese": "",
            "source": "word-by-word-index",
            "sourceRefs": refs,
            "sourcePages": pages,
            "placements": placements,
            "alternatePlacements": placements[1:],
            "sourceLine": entry.line,
            "theme": theme,
            "topic": topic,
            "partOfSpeech": "index entry",
            "ipa": "",
            "prefix": get_prefix(entry.text),
            "suffix": get_suffix(entry.text),
            "roots": [],
            "syllableType": get_syllable_type(entry.text),
            "vowelTeams": [team for team in VOWEL_TEAMS if team in normalized],
            "compound": entry.text.casefold() not in NON_COMPOUND_PHRASES and bool(re.search(r"[\s-]", entry.text)),
        }
        report["missingIpa"].append(entry.text)
        entries.append(word)

    counts = Counter(entry["theme"] for entry in entries)
    report["summary"] = {
        "rawLines": len(raw_text.splitlines()),
        "parsedEntries": len(parsed),
        "uniqueEntries": len(entries),
        "themeCounts": dict(sorted(counts.items())),
    }
    return entries, report


def main() -> int:
    raw_text = RAW_PATH.read_text(encoding="utf-8")
    entries, report = build_entries(raw_text)
    JSON_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JS_PATH.write_text(
        "window.LEARNING_DICTIONARY_FULL = "
        + json.dumps(entries, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
