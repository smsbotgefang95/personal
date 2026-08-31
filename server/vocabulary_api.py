#!/usr/bin/env python3
"""Small same-origin API for shared personal site data."""

import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_PAYLOAD = {"labels": {}, "meanings": {}, "updatedAt": None}
DEFAULT_LIFE_EVENTS_PAYLOAD = {"events": [], "deletedImportIds": [], "topicOrderByArea": {}, "hiddenTopicRows": {}, "updatedAt": None}
DEFAULT_TIME_ENTRIES_PAYLOAD = {"entries": [], "activeEntry": None, "taskOverrides": {}, "taskMerges": {}, "deletedEntryKeys": [], "updatedAt": None}
DEFAULT_SMART_SHOPPING_PAYLOAD = {"itemEdits": {}, "itemAdds": {}, "customBrandOptions": [], "itemPurchases": {}, "itemRemovals": {}, "itemRestorations": {}, "itemMoves": {}, "updatedAt": None}
DEFAULT_LEARNING_ENGLISH_CUSTOM_PAYLOAD = {"vocabulary": [], "sentences": [], "chunks": [], "dialogues": [], "updatedAt": None}
TIME_ENTRIES_MAX_BODY_BYTES = 16 * 1024 * 1024
DEFAULT_QUESTION_PROGRESS = {
    "1": "review",
    "27": "learned",
    "28": "learned",
    "42": "review",
    "50": "learning",
    "68": "tolearn",
    "69": "tolearn",
    "91": "tolearn",
    "92": "tolearn",
    "93": "tolearn",
    "99": "review",
}
DEFAULT_QUESTION_PROGRESS_PAYLOAD = {"progress": DEFAULT_QUESTION_PROGRESS, "updatedAt": None}
QUESTION_STATUSES = {"tolearn", "learning", "review", "learned"}
QUESTION_PROGRESS_LOCK = threading.Lock()


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
SMART_SHOPPING_DATA_PATH = env_path("SMART_SHOPPING_DATA_PATH", "~/personal-data/smart-shopping.json")
SMART_SHOPPING_ADMIN_KEY = os.environ.get("SMART_SHOPPING_ADMIN_KEY", ADMIN_KEY)
QUESTION_PROGRESS_DATA_PATH = env_path("QUESTION_PROGRESS_DATA_PATH", "~/personal-data/question-progress.json")
LEARNING_ENGLISH_CUSTOM_DATA_PATH = env_path("LEARNING_ENGLISH_CUSTOM_DATA_PATH", "~/personal-data/learning-english-custom.json")
LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH = os.environ.get("LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH")
LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH = Path(LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH).expanduser() if LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH else None
LEARNING_ENGLISH_CUSTOM_REPO_DATA_PATH = REPO_DIR / "data" / "learning-english-custom.json"
LEARNING_ENGLISH_CUSTOM_ADMIN_KEY = os.environ.get("LEARNING_ENGLISH_CUSTOM_ADMIN_KEY", ADMIN_KEY)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_VOCAB_MODEL = os.environ.get("OPENAI_VOCAB_MODEL", "gpt-4o-mini")


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


VOCAB_THEMES = {
    "",
    "color",
    "family",
    "body",
    "food",
    "time",
    "country",
    "place",
    "nature",
    "number",
    "feeling",
    "holiday",
    "clothes",
    "furniture",
    "sports",
    "appliance",
}
VOCAB_PREFIXES = {"none", "re", "un", "in", "im", "il", "ir", "dis", "pre", "pro", "over", "under", "mis", "non", "de", "en", "em", "out", "sub", "super", "trans"}
VOCAB_SUFFIXES = {"none", "s", "ed", "ly", "er", "est", "tion", "ment", "ness", "able", "ful", "less"}
VOCAB_ROOTS = {"form", "ject", "duce", "fact", "act", "sect", "sign", "port"}
VOCAB_SYLLABLES = {"", "open", "closed", "silent_e", "vowel_team", "r_controlled", "consonant_le"}
VOCAB_VOWEL_TEAMS = {"ai", "ay", "ea", "ee", "ei", "ey", "ie", "oa", "oe", "oi", "oy", "oo", "ou", "ow", "ue", "ui"}
VOCAB_IPA_SOUNDS = {"iː", "i", "ɪ", "e", "æ", "ɑː", "ɒ", "ɔː", "ʊ", "uː", "ʌ", "ɜː", "ə", "eɪ", "aɪ", "ɔɪ", "əʊ", "aʊ", "ɪə", "eə", "ʊə", "p", "b", "t", "d", "k", "ɡ", "g", "f", "v", "θ", "ð", "s", "z", "ʃ", "ʒ", "h", "tʃ", "dʒ", "m", "n", "ŋ", "l", "r", "j", "w"}


def clean_vocab_text(value, limit=240):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.strip().split())[:limit]


def clean_vocab_word(value):
    word = clean_vocab_text(value, 80)
    return word if 1 <= len(word) <= 80 else ""


def clean_vocab_choice(value, allowed, fallback):
    item = clean_vocab_text(value, 40).lower()
    return item if item in allowed else fallback


def clean_vocab_list(value, allowed):
    if not isinstance(value, list):
        value = []
    cleaned = []
    seen = set()
    for item in value[:12]:
        item = clean_vocab_text(item, 40).lower()
        if item and item in allowed and item not in seen:
            seen.add(item)
            cleaned.append(item)
    return cleaned


def clean_vocab_vowel_team_sounds(value, teams):
    if not isinstance(value, dict):
        return {}
    allowed_teams = set(teams)
    cleaned = {}
    for team, sound in value.items():
        team = clean_vocab_text(team, 12).lower()
        sound = clean_vocab_text(sound, 12).replace("oʊ", "əʊ")
        if team in allowed_teams and sound in VOCAB_IPA_SOUNDS:
            cleaned[team] = "ɡ" if sound == "g" else sound
    return cleaned


def clean_learning_id(value, fallback):
    item = clean_vocab_text(value, 120).lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in item).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:120] or fallback


def split_words(value):
    if isinstance(value, list):
        items = value
    else:
        items = str(value or "").replace("-", " ").split()
    cleaned = []
    seen = set()
    for item in items[:12]:
        word = clean_vocab_text(item, 40).lower().strip(".,!?;:\"'()[]{}")
        if word and word not in seen:
            seen.add(word)
            cleaned.append(word)
    return cleaned


def clean_autofill_item(value, requested_word):
    if not isinstance(value, dict):
        value = {}
    word = clean_vocab_word(value.get("word")) or requested_word
    vowel_teams = clean_vocab_list(value.get("vowelTeams"), VOCAB_VOWEL_TEAMS)
    return {
        "word": word,
        "chinese": clean_vocab_text(value.get("chinese"), 160),
        "scenario": "custom",
        "partOfSpeech": clean_vocab_text(value.get("partOfSpeech"), 80) or "custom word",
        "pronunciation": clean_vocab_text(value.get("pronunciation"), 120),
        "example": clean_vocab_text(value.get("example"), 220),
        "theme": clean_vocab_choice(value.get("theme"), VOCAB_THEMES, ""),
        "isCompound": bool(value.get("isCompound")) if isinstance(value.get("isCompound"), bool) else (" " in word),
        "prefix": clean_vocab_choice(value.get("prefix"), VOCAB_PREFIXES, "none"),
        "suffix": clean_vocab_choice(value.get("suffix"), VOCAB_SUFFIXES, "none"),
        "roots": clean_vocab_list(value.get("roots"), VOCAB_ROOTS),
        "syllableType": clean_vocab_choice(value.get("syllableType"), VOCAB_SYLLABLES, ""),
        "vowelTeams": vowel_teams,
        "vowelTeamSounds": clean_vocab_vowel_team_sounds(value.get("vowelTeamSounds"), vowel_teams),
        "ipa": clean_vocab_text(value.get("ipa"), 120),
        "isCustom": True,
        "rank": "Custom",
    }


def clean_custom_sentence(value, idx=0):
    if not isinstance(value, dict):
        value = {}
    english = clean_vocab_text(value.get("english") or value.get("sentence"), 220)
    if not english:
        return None
    return {
        "id": clean_learning_id(value.get("id"), f"custom-sentence-{idx + 1}"),
        "scenario": "learning",
        "english": english,
        "chinese": clean_vocab_text(value.get("chinese"), 220),
        "pronunciation": clean_vocab_text(value.get("pronunciation"), 160),
        "usage": clean_vocab_text(value.get("usage"), 260) or "Use this to practice a custom vocabulary word.",
        "isCustom": True,
    }


def clean_custom_chunk(value, idx=0, word=""):
    if not isinstance(value, dict):
        value = {}
    phrase = clean_vocab_text(value.get("phrase") or value.get("chunk"), 120)
    if not phrase:
        return None
    chunk_type = clean_vocab_text(value.get("type"), 40)
    if chunk_type not in {"collocation", "idiom", "phrasal-verb", "fixed-expression", "cliche", "sentence-frame", "functional-chunk", "noun-phrase", "compound-chunk"}:
        chunk_type = "collocation"
    words = split_words(value.get("words"))
    if not words and word:
        words = split_words(word)
    return {
        "id": clean_learning_id(value.get("id"), f"custom-chunk-{idx + 1}"),
        "phrase": phrase,
        "chinese": clean_vocab_text(value.get("chinese"), 160),
        "pronunciation": clean_vocab_text(value.get("pronunciation"), 120),
        "words": words,
        "type": chunk_type,
        "isCustom": True,
    }


def clean_custom_dialogue(value, idx=0):
    if not isinstance(value, dict):
        value = {}
    title = clean_vocab_text(value.get("title"), 120) or "Custom practice"
    incoming_lines = value.get("lines") if isinstance(value.get("lines"), list) else []
    lines = []
    for line_idx, line in enumerate(incoming_lines[:8]):
        if not isinstance(line, dict):
            continue
        english = clean_vocab_text(line.get("english"), 220)
        if not english:
            continue
        lines.append({
            "speaker": clean_vocab_text(line.get("speaker"), 20) or ("A" if line_idx % 2 == 0 else "B"),
            "english": english,
            "chinese": clean_vocab_text(line.get("chinese"), 220),
            "pronunciation": clean_vocab_text(line.get("pronunciation"), 160),
        })
    if not lines:
        return None
    return {
        "id": clean_learning_id(value.get("id"), f"custom-dialogue-{idx + 1}"),
        "scenario": "learning",
        "title": title,
        "chineseTitle": clean_vocab_text(value.get("chineseTitle"), 120) or "自定义练习",
        "context": clean_vocab_text(value.get("context"), 240) or "Custom vocabulary practice.",
        "lines": lines,
        "isCustom": True,
    }


def clean_learning_english_custom_payload(value):
    if not isinstance(value, dict):
        value = {}
    vocabulary = []
    seen_words = set()
    incoming_vocabulary = value.get("vocabulary", [])
    if not isinstance(incoming_vocabulary, list):
        incoming_vocabulary = []
    for item in incoming_vocabulary[:1000]:
        requested_word = clean_vocab_word(item.get("word")) if isinstance(item, dict) else ""
        cleaned = clean_autofill_item(item, requested_word)
        key = cleaned["word"].casefold()
        if key and key not in seen_words:
            seen_words.add(key)
            vocabulary.append(cleaned)
    sentences = []
    seen_sentences = set()
    for idx, item in enumerate(value.get("sentences", []) if isinstance(value.get("sentences"), list) else []):
        cleaned = clean_custom_sentence(item, idx)
        key = cleaned["english"].casefold() if cleaned else ""
        if key and key not in seen_sentences:
            seen_sentences.add(key)
            sentences.append(cleaned)
    chunks = []
    seen_chunks = set()
    for idx, item in enumerate(value.get("chunks", []) if isinstance(value.get("chunks"), list) else []):
        cleaned = clean_custom_chunk(item, idx)
        key = cleaned["phrase"].casefold() if cleaned else ""
        if key and key not in seen_chunks:
            seen_chunks.add(key)
            chunks.append(cleaned)
    dialogues = []
    seen_dialogues = set()
    for idx, item in enumerate(value.get("dialogues", []) if isinstance(value.get("dialogues"), list) else []):
        cleaned = clean_custom_dialogue(item, idx)
        key = cleaned["id"] if cleaned else ""
        if key and key not in seen_dialogues:
            seen_dialogues.add(key)
            dialogues.append(cleaned)
    return {
        "vocabulary": vocabulary,
        "sentences": sentences,
        "chunks": chunks,
        "dialogues": dialogues,
        "updatedAt": value.get("updatedAt"),
    }


def clean_autofill_package(value, requested_word):
    if not isinstance(value, dict):
        value = {}
    item_source = value.get("item") if isinstance(value.get("item"), dict) else value
    item = clean_autofill_item(item_source, requested_word)
    sentences = []
    for idx, sentence in enumerate(value.get("sentences", []) if isinstance(value.get("sentences"), list) else []):
        cleaned = clean_custom_sentence(sentence, idx)
        if cleaned:
            cleaned["id"] = clean_learning_id(cleaned["id"], f"custom-{item['word']}-sentence-{idx + 1}")
            sentences.append(cleaned)
    chunks = []
    for idx, chunk in enumerate(value.get("chunks", []) if isinstance(value.get("chunks"), list) else []):
        cleaned = clean_custom_chunk(chunk, idx, item["word"])
        if cleaned:
            cleaned["id"] = clean_learning_id(cleaned["id"], f"custom-{item['word']}-chunk-{idx + 1}")
            chunks.append(cleaned)
    dialogues = []
    for idx, dialogue in enumerate(value.get("dialogues", []) if isinstance(value.get("dialogues"), list) else []):
        cleaned = clean_custom_dialogue(dialogue, idx)
        if cleaned:
            cleaned["id"] = clean_learning_id(cleaned["id"], f"custom-{item['word']}-dialogue-{idx + 1}")
            dialogues.append(cleaned)
    return {"item": item, "sentences": sentences[:3], "chunks": chunks[:4], "dialogues": dialogues[:1]}


def extract_json_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object in model response")
    return json.loads(text[start : end + 1])


def openai_vocabulary_autofill(word):
    if not OPENAI_API_KEY:
        return None, "openai_key_missing"
    schema_hint = {
        "word": word,
        "chinese": "简体中文释义",
        "scenario": "custom",
        "partOfSpeech": "noun / verb / adjective / adverb / phrase / etc.",
        "pronunciation": "plain beginner-friendly pronunciation hint",
        "example": "short simple English example sentence",
        "theme": "one of: color, family, body, food, time, country, place, nature, number, feeling, holiday, clothes, furniture, sports, appliance, or empty string",
        "isCompound": False,
        "prefix": "one of known prefixes or none",
        "suffix": "one of known suffixes or none",
        "roots": ["only known roots: form, ject, duce, fact, act, sect, sign, port"],
        "syllableType": "open, closed, silent_e, vowel_team, r_controlled, consonant_le, or empty string",
        "vowelTeams": ["known vowel teams appearing in the word"],
        "vowelTeamSounds": {"ea": "iː"},
        "ipa": "IPA without slash marks",
        "isCustom": True,
        "rank": "Custom",
    }
    package_hint = {
        "item": schema_hint,
        "chunks": [
            {
                "phrase": f"use {word}",
                "chinese": "简体中文释义",
                "pronunciation": "plain beginner-friendly pronunciation hint",
                "words": ["use", word],
                "type": "collocation",
            }
        ],
        "sentences": [
            {
                "english": f"I can use {word} in a sentence.",
                "chinese": "简体中文句子翻译",
                "pronunciation": "plain beginner-friendly pronunciation hint",
                "usage": "short learner-facing usage note",
            }
        ],
        "dialogues": [
            {
                "title": f"Practice {word}",
                "chineseTitle": "练习词汇",
                "context": "short beginner practice conversation",
                "lines": [
                    {"speaker": "A", "english": f"What does {word} mean?", "chinese": "简体中文翻译", "pronunciation": "plain pronunciation hint"},
                    {"speaker": "B", "english": f"It means {word}.", "chinese": "简体中文翻译", "pronunciation": "plain pronunciation hint"},
                ],
            }
        ],
    }
    prompt = (
        "Return only valid JSON for an English learner custom practice package. "
        "Use simple beginner-friendly English. Use Simplified Chinese for chinese and chineseTitle. "
        "Do not wrap the JSON in markdown. Fill every field. "
        "If a field is not applicable, use an empty string, empty array, empty object, false, none, or Custom as appropriate. "
        "The top-level JSON must have item, chunks, sentences, and dialogues. "
        "item is the vocabulary card. chunks must contain 2 to 4 useful chunks using the word. "
        "sentences must contain 2 to 3 short example sentences using the word. "
        "dialogues must contain exactly 1 short beginner dialogue with 2 to 4 lines using the word naturally. "
        "Allowed chunk types: collocation, idiom, phrasal-verb, fixed-expression, cliche, sentence-frame, functional-chunk, noun-phrase, compound-chunk. "
        f"Allowed prefixes: {sorted(VOCAB_PREFIXES)}. "
        f"Allowed suffixes: {sorted(VOCAB_SUFFIXES)}. "
        f"Allowed roots: {sorted(VOCAB_ROOTS)}. "
        f"Allowed themes: {sorted(VOCAB_THEMES)}. "
        f"Allowed vowel teams: {sorted(VOCAB_VOWEL_TEAMS)}. "
        f"Schema example: {json.dumps(package_hint, ensure_ascii=False)}. "
        f"Word or phrase: {word}"
    )
    payload = {
        "model": OPENAI_VOCAB_MODEL,
        "messages": [
            {"role": "system", "content": "You are a careful English vocabulary assistant that returns strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1000]
        return None, f"openai_http_{exc.code}: {detail}"
    except Exception as exc:
        return None, f"openai_request_failed: {exc}"
    try:
        content = body["choices"][0]["message"]["content"]
        return extract_json_object(content), None
    except Exception as exc:
        return None, f"openai_parse_failed: {exc}"


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


def clean_topic_order_by_area(value):
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for area, topics in list(value.items())[:100]:
        area = str(area).strip()[:80]
        if not area or not isinstance(topics, list):
            continue
        seen = set()
        clean_topics = []
        for topic in topics[:300]:
            topic = str(topic).strip()[:120]
            if not topic or topic in seen:
                continue
            seen.add(topic)
            clean_topics.append(topic)
        if clean_topics:
            cleaned[area] = clean_topics
    return cleaned


def clean_hidden_topic_rows(value):
    return clean_topic_order_by_area(value)


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
        "topicOrderByArea": clean_topic_order_by_area(value.get("topicOrderByArea")),
        "hiddenTopicRows": clean_hidden_topic_rows(value.get("hiddenTopicRows")),
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


def clean_due_time(value):
    value = clean_time_text(value, 20)
    if not value:
        return ""
    parts = value.split(":")
    if len(parts) != 2:
        return ""
    hour, minute = parts[0], parts[1]
    if not (hour.isdigit() and minute.isdigit()):
        return ""
    hour_number = int(hour)
    minute_number = int(minute)
    if not (0 <= hour_number <= 23 and 0 <= minute_number <= 59):
        return ""
    return f"{hour_number:02d}:{minute_number:02d}"


def clean_recurrence(value):
    value = clean_time_text(value, 20).lower()
    return value if value in {"none", "daily", "weekly", "monthly", "yearly", "custom"} else "none"


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
            "dueDateManaged": item.get("dueDateManaged") is True,
            "dueTime": clean_due_time(item.get("dueTime")),
            "dueDateEditedAt": clean_time_text(item.get("dueDateEditedAt"), 40),
            "dueDateManualHold": clean_due_date(item.get("dueDateManualHold")),
            "status": "done" if item.get("status") == "done" else "todo",
            "recurrence": recurrence,
            "recurringText": clean_time_text(item.get("recurringText"), 120) if recurrence == "custom" else "",
            "taskOrder": clean_time_text(item.get("taskOrder"), 80),
            "autoDoneDate": clean_due_date(item.get("autoDoneDate")),
            "privateTask": item.get("privateTask") is True,
            "notes": clean_time_text(item.get("notes"), 4000),
            "updatedAt": clean_time_text(item.get("updatedAt"), 40),
        }
        metadata_fields_present = False
        for field, max_length in {
            "listId": 80,
            "taskName": 240,
            "department": 160,
            "priority": 80,
            "section": 160,
            "taskCategory": 120,
            "taskType": 80,
        }.items():
            if field in item:
                metadata_fields_present = True
                override[field] = clean_time_text(item.get(field), max_length)
        if (
            override["dueDate"]
            or override["dueDateManaged"]
            or override["dueTime"]
            or override["dueDateEditedAt"]
            or override["dueDateManualHold"]
            or override["status"] == "done"
            or override["recurrence"] != "none"
            or override["recurringText"]
            or override["taskOrder"]
            or override["autoDoneDate"]
            or override["privateTask"]
            or override["notes"]
            or metadata_fields_present
        ):
            overrides[key] = override
        elif item.get("dueDate") == "" or item.get("dueTime") == "" or item.get("dueDateManualHold") == "" or item.get("taskOrder") == "" or item.get("notes") == "":
            overrides[key] = override
    return overrides


def clean_task_merges(value):
    if not isinstance(value, dict):
        return {}
    merges = {}
    for key, item in list(value.items())[:5000]:
        key = clean_time_text(key, 260)
        if "|||" not in key or not isinstance(item, dict):
            continue
        target_key = clean_time_text(item.get("targetKey"), 260)
        if "|||" not in target_key:
            continue
        target_parts = target_key.split("|||", 1)
        target_list_id = clean_time_text(item.get("targetListId"), 80) or target_parts[0]
        target_task_id = clean_time_text(item.get("targetTaskId"), 160) or target_parts[1]
        task_name = clean_time_text(item.get("taskName"), 240)
        if key == target_key and not task_name:
            continue
        merges[key] = {
            "targetKey": target_key,
            "targetListId": target_list_id,
            "targetTaskId": target_task_id,
            "taskName": task_name,
            "updatedAt": clean_time_text(item.get("updatedAt"), 40),
        }
    return merges


def clean_deleted_time_entry_keys(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    seen = set()
    for item in value[:10000]:
        item = str(item).strip()[:320]
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


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
        "dueTime": clean_due_time(value.get("dueTime")),
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
        "taskMerges": clean_task_merges(value.get("taskMerges")),
        "deletedEntryKeys": clean_deleted_time_entry_keys(value.get("deletedEntryKeys")),
        "updatedAt": value.get("updatedAt"),
    }


def load_time_entries_payload():
    try:
        with TIME_ENTRIES_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        payload = DEFAULT_TIME_ENTRIES_PAYLOAD.copy()
    return clean_time_entries_payload(payload)


def clean_question_index(value):
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= idx <= 999:
        return str(idx)
    return None


def clean_question_progress_payload(value):
    if not isinstance(value, dict):
        value = {}
    incoming = value.get("progress", value)
    if not isinstance(incoming, dict):
        incoming = {}
    progress = {}
    for key, status in incoming.items():
        idx = clean_question_index(key)
        if idx is None or status not in QUESTION_STATUSES:
            continue
        progress[idx] = status
    return {
        "progress": progress,
        "updatedAt": value.get("updatedAt"),
    }


def load_question_progress_payload():
    try:
        with QUESTION_PROGRESS_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        payload = DEFAULT_QUESTION_PROGRESS_PAYLOAD.copy()
    return clean_question_progress_payload(payload)


def load_learning_english_custom_payload():
    try:
        with LEARNING_ENGLISH_CUSTOM_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        try:
            with LEARNING_ENGLISH_CUSTOM_REPO_DATA_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            payload = DEFAULT_LEARNING_ENGLISH_CUSTOM_PAYLOAD.copy()
    return clean_learning_english_custom_payload(payload)


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


def sync_learning_english_custom_to_git(payload):
    if not GIT_SYNC or not (REPO_DIR / ".git").exists():
        return {"status": "skipped"}
    try:
        atomic_write(LEARNING_ENGLISH_CUSTOM_REPO_DATA_PATH, payload)
        add = run_git(["add", "data/learning-english-custom.json"])
        if add.returncode != 0:
            return {"status": "failed", "error": add.stderr.strip() or add.stdout.strip()}
        diff = run_git(["diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            return {"status": "unchanged"}
        commit = run_git([
            "-c", "user.name=Personal Learning English Bot",
            "-c", "user.email=learning-english-bot@personal.homehomehooray.com",
            "commit", "-m", "Update custom learning English content",
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

def load_smart_shopping_payload():
    try:
        with SMART_SHOPPING_DATA_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return {**DEFAULT_SMART_SHOPPING_PAYLOAD, **payload}
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_SMART_SHOPPING_PAYLOAD.copy()

def clean_smart_shopping_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    cleaned = DEFAULT_SMART_SHOPPING_PAYLOAD.copy()
    for key in ("itemEdits", "itemAdds", "itemPurchases", "itemRemovals", "itemRestorations", "itemMoves"):
        value = payload.get(key, {})
        cleaned[key] = value if isinstance(value, dict) else {}
    value = payload.get("customBrandOptions", [])
    cleaned["customBrandOptions"] = value if isinstance(value, list) else []
    cleaned["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return cleaned

def write_smart_shopping(payload):
    atomic_write(SMART_SHOPPING_DATA_PATH, payload)
    return {"status": "stored"}


def write_question_progress(payload):
    atomic_write(QUESTION_PROGRESS_DATA_PATH, payload)
    return {"status": "stored"}


def write_learning_english_custom(payload):
    atomic_write(LEARNING_ENGLISH_CUSTOM_DATA_PATH, payload)
    if LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH:
        atomic_write(LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH, payload)
    git_result = sync_learning_english_custom_to_git(payload)
    if LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH:
        atomic_write(LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH, payload)
    return git_result


class Handler(BaseHTTPRequestHandler):
    server_version = "VocabularyAPI/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Vocab-Admin-Key, X-Life-Events-Admin-Key, X-Time-Tracking-Admin-Key, X-Learning-English-Admin-Key")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Vocab-Admin-Key, X-Life-Events-Admin-Key, X-Time-Tracking-Admin-Key, X-Learning-English-Admin-Key")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_PATCH(self):
        if self.path.split("?", 1)[0] != "/api/smart-shopping/item":
            self.send_error(404)
            return
        if SMART_SHOPPING_ADMIN_KEY and self.headers.get("X-Smart-Shopping-Admin-Key") != SMART_SHOPPING_ADMIN_KEY:
            self.send_json(401, {"ok": False, "error": "admin_key_required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            incoming = json.loads(self.rfile.read(length).decode("utf-8"))
            storage_key = str(incoming.get("storageKey", ""))
            facts = incoming.get("facts")
            if not storage_key or not isinstance(facts, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"ok": False, "error": "invalid_item_update"})
            return
        payload = load_smart_shopping_payload()
        existing = payload["itemEdits"].get(storage_key, {})
        existing["facts"] = {**existing.get("facts", {}), **facts}
        payload["itemEdits"][storage_key] = existing
        payload = clean_smart_shopping_payload(payload)
        write_smart_shopping(payload)
        self.send_json(200, {"ok": True, "facts": payload["itemEdits"][storage_key]["facts"]})

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/time-entries":
            if TIME_ENTRIES_ADMIN_KEY and self.headers.get("X-Time-Tracking-Admin-Key") != TIME_ENTRIES_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            self.send_json(200, load_time_entries_payload())
            return
        if path == "/api/smart-shopping":
            if SMART_SHOPPING_ADMIN_KEY and self.headers.get("X-Smart-Shopping-Admin-Key") != SMART_SHOPPING_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            self.send_json(200, load_smart_shopping_payload())
            return
        if path == "/api/life-events":
            self.send_json(200, load_life_events_payload())
            return
        if path == "/api/citizenship/question-progress":
            self.send_json(200, load_question_progress_payload())
            return
        if path == "/api/learning-english/custom":
            self.send_json(200, load_learning_english_custom_payload())
            return
        if path != "/api/vocabulary-overrides":
            self.send_error(404)
            return
        self.send_json(200, load_payload())

    def do_PUT(self):
        path = self.path.split("?", 1)[0]
        prefix = "/api/citizenship/question-progress/"
        if not path.startswith(prefix):
            self.send_error(404)
            return
        idx = clean_question_index(path.removeprefix(prefix))
        if idx is None:
            self.send_json(400, {"ok": False, "error": "invalid_question_index"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 1024 * 16))
            incoming = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"ok": False, "error": "invalid_json"})
            return
        status = incoming.get("status")
        if status not in QUESTION_STATUSES:
            self.send_json(400, {"ok": False, "error": "invalid_status"})
            return
        with QUESTION_PROGRESS_LOCK:
            payload = load_question_progress_payload()
            payload["progress"][idx] = status
            payload["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_result = write_question_progress(payload)
        self.send_json(200, {"ok": True, "payload": payload, "result": write_result})

    def do_DELETE(self):
        path = self.path.split("?", 1)[0]
        prefix = "/api/citizenship/question-progress/"
        if not path.startswith(prefix):
            self.send_error(404)
            return
        idx = clean_question_index(path.removeprefix(prefix))
        if idx is None:
            self.send_json(400, {"ok": False, "error": "invalid_question_index"})
            return
        with QUESTION_PROGRESS_LOCK:
            payload = load_question_progress_payload()
            payload["progress"].pop(idx, None)
            payload["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_result = write_question_progress(payload)
        self.send_json(200, {"ok": True, "payload": payload, "result": write_result})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/time-entries":
            if TIME_ENTRIES_ADMIN_KEY and self.headers.get("X-Time-Tracking-Admin-Key") != TIME_ENTRIES_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > TIME_ENTRIES_MAX_BODY_BYTES:
                    self.send_json(413, {"ok": False, "error": "payload_too_large", "maxBytes": TIME_ENTRIES_MAX_BODY_BYTES})
                    return
                raw = self.rfile.read(length)
                incoming = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, {"ok": False, "error": "invalid_json"})
                return
            payload = clean_time_entries_payload(incoming)
            payload["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_result = write_time_entries(payload)
            self.send_json(200, {"ok": True, "payload": payload, "git": write_result})
            return
        if path == "/api/smart-shopping":
            if SMART_SHOPPING_ADMIN_KEY and self.headers.get("X-Smart-Shopping-Admin-Key") != SMART_SHOPPING_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                incoming = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, {"ok": False, "error": "invalid_json"})
                return
            payload = clean_smart_shopping_payload(incoming)
            write_smart_shopping(payload)
            self.send_json(200, {"ok": True, "payload": payload})
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
        if path == "/api/learning-english/vocabulary-autofill":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(min(length, 1024 * 16))
                incoming = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, {"ok": False, "error": "invalid_json"})
                return
            word = clean_vocab_word(incoming.get("word"))
            if not word:
                self.send_json(400, {"ok": False, "error": "invalid_word"})
                return
            generated, error = openai_vocabulary_autofill(word)
            if error:
                status = 503 if error == "openai_key_missing" else 502
                self.send_json(status, {"ok": False, "error": error})
                return
            package = clean_autofill_package(generated, word)
            self.send_json(200, {"ok": True, "item": package["item"], "package": package})
            return
        if path == "/api/learning-english/custom":
            if LEARNING_ENGLISH_CUSTOM_ADMIN_KEY and self.headers.get("X-Learning-English-Admin-Key") != LEARNING_ENGLISH_CUSTOM_ADMIN_KEY:
                self.send_json(401, {"ok": False, "error": "admin_key_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(min(length, 1024 * 512))
                incoming = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, {"ok": False, "error": "invalid_json"})
                return
            payload = clean_learning_english_custom_payload(incoming)
            payload["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            git_result = write_learning_english_custom(payload)
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
    SMART_SHOPPING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SMART_SHOPPING_DATA_PATH.exists():
        write_smart_shopping(DEFAULT_SMART_SHOPPING_PAYLOAD.copy())
    QUESTION_PROGRESS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not QUESTION_PROGRESS_DATA_PATH.exists():
        write_question_progress(DEFAULT_QUESTION_PROGRESS_PAYLOAD.copy())
    LEARNING_ENGLISH_CUSTOM_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LEARNING_ENGLISH_CUSTOM_DATA_PATH.exists():
        write_learning_english_custom(DEFAULT_LEARNING_ENGLISH_CUSTOM_PAYLOAD.copy())
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Vocabulary API listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
