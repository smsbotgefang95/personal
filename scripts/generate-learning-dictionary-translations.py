#!/usr/bin/env python3
"""Generate Simplified Chinese translations for Word by Word dictionary entries."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_PATH = ROOT / "data" / "learning-dictionary-full.json"
TRANSLATIONS_PATH = ROOT / "data" / "learning-dictionary-translations.zh-CN.json"
REPORT_PATH = ROOT / "data" / "learning-dictionary-translations-report.json"
DEFAULT_MODEL = os.environ.get("OPENAI_VOCAB_MODEL", "gpt-4o-mini")
DEFAULT_BATCH_SIZE = 80
MAX_RETRIES = 3


OCR_SUSPICIOUS_RE = re.compile(
    r"(?:[A-Z]{3,}|[0-9]|[íìîïáàâäéèêëóòôöúùûüñ]|rn|l'rn|Helio|rnail|c1|inq|qes|00)",
    re.IGNORECASE,
)
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="entries per API request")
    parser.add_argument("--limit", type=int, default=0, help="maximum missing entries to translate")
    parser.add_argument("--refresh", action="store_true", help="regenerate translations that already exist")
    parser.add_argument("--dry-run", action="store_true", help="report missing entries without API calls or writes")
    return parser.parse_args()


def load_json_object(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_dictionary() -> list[dict]:
    data = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{DICTIONARY_PATH} must contain a JSON array")
    return data


def clean_translation(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" -:;,.，。；：")
    return text[:80]


def entry_key(entry: dict) -> str:
    return str(entry.get("word") or entry.get("text") or "").strip()


def is_low_confidence(word: str, translation: str) -> bool:
    if not translation or not CHINESE_RE.search(translation):
        return True
    return bool(OCR_SUSPICIOUS_RE.search(word))


def get_missing_entries(entries: list[dict], translations: dict, refresh: bool) -> list[dict]:
    missing = []
    seen = set()
    for entry in entries:
        word = entry_key(entry)
        if not word or word in seen:
            continue
        seen.add(word)
        existing = clean_translation(translations.get(word))
        if refresh or not existing:
            missing.append(entry)
    return missing


def duplicate_keys(entries: list[dict]) -> list[str]:
    counts = Counter(entry_key(entry) for entry in entries if entry_key(entry))
    return sorted(key for key, count in counts.items() if count > 1)


def make_prompt(batch: list[dict]) -> str:
    items = [
        {
            "word": entry_key(entry),
            "theme": entry.get("theme", ""),
            "topic": entry.get("topic", ""),
            "sourceRefs": entry.get("sourceRefs", []),
        }
        for entry in batch
    ]
    return (
        "Translate these English learner dictionary entries into concise Simplified Chinese. "
        "Return only valid JSON with one property named translations. "
        "translations must be an object keyed by the exact English word string provided. "
        "Values must be short learner-facing meanings, usually 1 to 8 Chinese characters or a short phrase. "
        "Do not write explanations, examples, pinyin, or English in the translation value. "
        "Use the theme, topic, and sourceRefs only as context. "
        "If an entry appears OCR-corrupted or ambiguous, give the best likely learner meaning and keep it short. "
        f"Entries: {json.dumps(items, ensure_ascii=False)}"
    )


def parse_response_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object in model response")
    data = json.loads(text[start : end + 1])
    translations = data.get("translations") if isinstance(data, dict) else None
    if not isinstance(translations, dict):
        raise ValueError("Model response missing translations object")
    return translations


def request_batch(api_key: str, model: str, batch: list[dict]) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a careful English-Chinese dictionary translator. Return strict JSON only."},
            {"role": "user", "content": make_prompt(batch)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.loads(response.read().decode("utf-8"))
    return parse_response_json(body["choices"][0]["message"]["content"])


def generate_batch(api_key: str, model: str, batch: list[dict]) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return request_batch(api_key, model, batch)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as error:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"translation batch failed after {MAX_RETRIES} attempts: {error}") from error
            time.sleep(2**attempt)
    return {}


def ordered_translations(translations: dict) -> dict:
    return dict(sorted(
        (str(key).strip(), clean_translation(value))
        for key, value in translations.items()
        if str(key).strip() and clean_translation(value)
    ))


def write_outputs(translations: dict, report: dict) -> None:
    TRANSLATIONS_PATH.write_text(json.dumps(ordered_translations(translations), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    entries = load_dictionary()
    translations = load_json_object(TRANSLATIONS_PATH)
    missing_entries = get_missing_entries(entries, translations, args.refresh)
    if args.limit > 0:
        missing_entries = missing_entries[: args.limit]

    report = {
        "model": args.model,
        "dictionaryEntries": len(entries),
        "existingTranslations": sum(1 for value in translations.values() if clean_translation(value)),
        "requestedTranslations": len(missing_entries),
        "translatedCount": 0,
        "stillMissingCount": 0,
        "duplicateKeys": duplicate_keys(entries),
        "lowConfidence": [],
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if args.dry_run:
        report["stillMissingCount"] = len(get_missing_entries(entries, translations, False))
        report["lowConfidence"] = [
            {"word": entry_key(entry), "theme": entry.get("theme", ""), "topic": entry.get("topic", "")}
            for entry in missing_entries
            if OCR_SUSPICIOUS_RE.search(entry_key(entry))
        ]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")

    batch_size = max(1, args.batch_size)
    for offset in range(0, len(missing_entries), batch_size):
        batch = missing_entries[offset : offset + batch_size]
        generated = generate_batch(api_key, args.model, batch)
        batch_words = {entry_key(entry) for entry in batch}
        for word in batch_words:
            translation = clean_translation(generated.get(word))
            if not translation:
                continue
            translations[word] = translation
            report["translatedCount"] += 1
            if is_low_confidence(word, translation):
                report["lowConfidence"].append({"word": word, "translation": translation})
        write_outputs(translations, report)
        print(f"translated {min(offset + len(batch), len(missing_entries))}/{len(missing_entries)}")

    report["stillMissingCount"] = len(get_missing_entries(entries, translations, False))
    report["lowConfidence"] = sorted(report["lowConfidence"], key=lambda item: item["word"].casefold())
    write_outputs(translations, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
