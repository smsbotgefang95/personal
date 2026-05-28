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
NON_COMPOUND_PHRASES = {"get up", "go shopping", "wash dishes"}

REF_TOKEN = r"\d{1,3}(?:[-~·.][~A-Za-z0-9]{1,3}){0,2}(?![A-Za-z0-9-])"
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


PAGE_TOPIC_STARTS = [
    (1, "personal", "Personal Information"),
    (2, "personal", "Family Members I"),
    (3, "personal", "Family Members II"),
    (4, "daily", "The Classroom"),
    (6, "daily", "Classroom Actions"),
    (8, "daily", "Prepositions"),
    (9, "daily", "Everyday Activities I"),
    (10, "daily", "Everyday Activities II"),
    (11, "daily", "Leisure Activities"),
    (12, "daily", "Everyday Conversation"),
    (14, "daily", "The Weather"),
    (15, "numbers", "Numbers"),
    (16, "numbers", "Time"),
    (17, "numbers", "Money"),
    (18, "numbers", "The Calendar"),
    (19, "numbers", "Time Expressions and Seasons"),
    (20, "home", "Types of Housing and Communities"),
    (21, "home", "The Living Room"),
    (22, "home", "The Dining Room"),
    (23, "home", "The Bedroom"),
    (24, "home", "The Kitchen"),
    (25, "home", "The Baby's Room"),
    (26, "home", "The Bathroom"),
    (27, "home", "Outside the Home"),
    (28, "home", "The Apartment Building"),
    (30, "home", "Household Problems and Repairs"),
    (32, "home", "Cleaning Your Home"),
    (33, "home", "Home Supplies"),
    (34, "home", "Tools and Hardware"),
    (35, "home", "Gardening Tools and Actions"),
    (36, "community", "Places Around Town I"),
    (38, "community", "Places Around Town II"),
    (40, "community", "The City"),
    (42, "describing", "People and Physical Descriptions"),
    (44, "describing", "Describing People and Things"),
    (46, "describing", "Describing Physical States and Emotions"),
    (48, "food", "Fruits"),
    (49, "food", "Vegetables"),
    (50, "food", "Meat, Poultry, and Seafood"),
    (51, "food", "Dairy Products, Juices, and Beverages"),
    (52, "food", "Deli, Frozen Foods, and Snack Foods"),
    (53, "food", "Groceries"),
    (54, "food", "Household Supplies, Baby Products, and Pet Food"),
    (55, "food", "The Supermarket"),
    (56, "food", "Containers and Quantities"),
    (57, "food", "Units of Measure"),
    (58, "food", "Food Preparation and Recipes"),
    (59, "food", "Kitchen Utensils and Cookware"),
    (60, "food", "Fast Food"),
    (61, "food", "The Coffee Shop and Sandwiches"),
    (62, "food", "The Restaurant"),
    (64, "food", "A Restaurant Menu"),
    (65, "clothes", "Colors"),
    (66, "clothes", "Clothing"),
    (67, "clothes", "Outerwear"),
    (68, "clothes", "Sleepwear and Underwear"),
    (69, "clothes", "Exercise Clothing and Footwear"),
    (70, "clothes", "Jewelry and Accessories"),
    (71, "clothes", "Describing Clothing"),
    (72, "clothes", "Clothing Problems and Alterations"),
    (73, "clothes", "Laundry"),
    (74, "shopping", "The Department Store"),
    (75, "shopping", "Shopping"),
    (76, "shopping", "Video and Audio Equipment"),
    (77, "shopping", "Telephones and Cameras"),
    (78, "shopping", "Computers"),
    (79, "shopping", "The Toy Store"),
    (80, "services", "The Bank"),
    (81, "services", "Finances"),
    (82, "services", "The Post Office"),
    (83, "services", "The Library"),
    (84, "services", "Community Institutions"),
    (85, "services", "Crime and Emergencies"),
    (86, "health", "The Body"),
    (88, "health", "Ailments, Symptoms, and Injuries"),
    (90, "health", "First Aid"),
    (91, "health", "Medical Emergencies and Illnesses"),
    (92, "health", "The Medical Exam"),
    (93, "health", "Medical and Dental Procedures"),
    (94, "health", "Medical Advice"),
    (95, "health", "Medicine"),
    (96, "health", "Medical Specialists"),
    (97, "health", "The Hospital"),
    (98, "health", "Personal Hygiene"),
    (100, "health", "Baby Care"),
    (101, "school", "Types of Schools"),
    (102, "school", "The School"),
    (103, "school", "School Subjects"),
    (104, "school", "Extracurricular Activities"),
    (105, "school", "Mathematics"),
    (106, "school", "Measurements and Geometric Shapes"),
    (107, "school", "English Language Arts and Composition"),
    (108, "school", "Literature and Writing"),
    (109, "school", "Geography"),
    (110, "school", "Science"),
    (111, "school", "The Universe"),
    (112, "work", "Occupations I"),
    (114, "work", "Occupations II"),
    (116, "work", "Job Skills and Activities"),
    (118, "work", "Job Search"),
    (119, "work", "The Workplace"),
    (120, "work", "Office Supplies and Equipment"),
    (121, "work", "The Factory"),
    (122, "work", "The Construction Site"),
    (123, "work", "Job Safety"),
    (124, "transportation", "Public Transportation"),
    (125, "transportation", "Types of Vehicles"),
    (126, "transportation", "Car Parts and Maintenance"),
    (128, "transportation", "Highways and Streets"),
    (129, "transportation", "Prepositions of Motion"),
    (130, "transportation", "Traffic Signs and Directions"),
    (131, "transportation", "The Airport"),
    (132, "transportation", "Airplane Travel"),
    (133, "transportation", "The Hotel"),
    (134, "recreation", "Hobbies, Crafts, and Games"),
    (136, "recreation", "Places to Go"),
    (137, "recreation", "The Park and the Playground"),
    (138, "recreation", "The Beach"),
    (139, "recreation", "Outdoor Recreation"),
    (140, "recreation", "Individual Sports and Recreation"),
    (142, "recreation", "Team Sports"),
    (143, "recreation", "Team Sports Equipment"),
    (144, "recreation", "Winter Sports and Recreation"),
    (145, "recreation", "Water Sports and Recreation"),
    (146, "recreation", "Sport and Exercise Actions"),
    (147, "recreation", "Entertainment"),
    (148, "recreation", "Types of Entertainment"),
    (150, "recreation", "Musical Instruments"),
    (151, "nature", "The Farm and Farm Animals"),
    (152, "nature", "Animals and Pets"),
    (154, "nature", "Birds and Insects"),
    (155, "nature", "Fish, Sea Animals, and Reptiles"),
    (156, "nature", "Trees, Plants, and Flowers"),
    (158, "nature", "Energy, Conservation, and the Environment"),
    (159, "nature", "Natural Disasters"),
    (160, "travel", "Types of Travel"),
    (161, "travel", "Arriving at a Destination"),
    (162, "travel", "Hotel Communication"),
    (163, "travel", "Tourist Activities"),
    (164, "travel", "Tourist Communication"),
    (166, "civics", "Maps"),
]

PAGE_TOPIC_RULES = [
    (range(start, PAGE_TOPIC_STARTS[index + 1][0]), theme, topic)
    for index, (start, theme, topic) in enumerate(PAGE_TOPIC_STARTS[:-1])
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


LEADING_OCR_MARKER_RE = re.compile(r"^[~·]\s*[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?\s+")
LEADING_REFERENCE_JUNK_RE = re.compile(r"""^(?:
    ['./\[]\s*\d |
    ['./\[]?\s*-\s*(?:['./\[]?\s*)?(?:\d|[A-Za-z]\b|[A-Za-z],) |
    \[\s*['’]?[A-Za-z]\b
)""", re.VERBOSE)


def normalize_entry_text(value: str) -> str:
    text = clean_entry_text(value)
    cleaned = clean_entry_text(LEADING_OCR_MARKER_RE.sub("", text))
    if cleaned and re.search(r"[A-Za-z]", cleaned):
        return cleaned
    if re.search(r"[A-Za-z]", text):
        return text
    return ""


def is_malformed_entry_text(value: str) -> bool:
    text = clean_entry_text(value)
    if not text:
        return True
    if not re.match(r"""^[A-Za-z0-9"]""", text):
        return True
    if LEADING_REFERENCE_JUNK_RE.match(text):
        return True
    return not re.search(r"[A-Za-z0-9]", text)


def normalize_ref_token(token: str) -> str:
    clean_token = token.strip()
    page_digit_ocr = re.fullmatch(r"(\d)[~·](\d)-([A-Za-z0-9]+)", clean_token)
    if page_digit_ocr:
        return f"{page_digit_ocr.group(1)}6{page_digit_ocr.group(2)}-{page_digit_ocr.group(3)}"

    dotted_page = re.fullmatch(r"(\d)\.(\d)-([A-Za-z0-9]+)", clean_token)
    if dotted_page:
        return f"{dotted_page.group(1)}{dotted_page.group(2)}-{dotted_page.group(3)}"

    missing_hyphen = re.fullmatch(r"(\d{1,3})[~·]([A-Za-z0-9]+)", clean_token)
    if missing_hyphen:
        return f"{missing_hyphen.group(1)}-{missing_hyphen.group(2)}"

    marked_item = re.fullmatch(r"(\d{1,3})-[~·]?([A-Za-z0-9]+)", clean_token)
    if marked_item:
        return f"{marked_item.group(1)}-{marked_item.group(2)}"

    return clean_token


def parse_ref_group(value: str) -> list[str]:
    refs: list[str] = []
    current_page = ""
    for token in [part.strip() for part in value.split(",") if part.strip()]:
        token = normalize_ref_token(token)
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
        "discardedMalformedEntries": [],
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
        normalized_text = normalize_entry_text(entry.text)
        if not normalized_text:
            report["unparsedLines"].append({"line": entry.line, "text": entry.text, "reason": "discarded marker-only entry"})
            continue
        if is_malformed_entry_text(normalized_text):
            report["discardedMalformedEntries"].append({"line": entry.line, "text": normalized_text, "refs": entry.refs})
            continue
        entry.text = normalized_text
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
