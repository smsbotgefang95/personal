#!/usr/bin/env python3
"""Generate static OpenAI TTS MP3 files for spoken text on the site."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "audio" / "openai-tts"
MODEL = "gpt-4o-mini-tts"
VOICE = "coral"
EN_INSTRUCTIONS = (
    "Speak slowly and clearly, like a warm English teacher helping a beginner "
    "learner. Use natural American English pronunciation."
)
ZH_INSTRUCTIONS = "Speak clearly and naturally in Mandarin Chinese for a language learner."


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fnv1a(value: str) -> str:
    hash_value = 0x811C9DC5
    for char in value:
        hash_value ^= ord(char)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return f"{hash_value:08x}"


def audio_path(text: str, lang: str) -> Path:
    key = f"{lang.lower()}|{VOICE}|{normalize_text(text)}"
    return OUTPUT_ROOT / lang.lower() / f"{fnv1a(key)}.mp3"


def decode_js_string(raw: str) -> str:
    return json.loads(f'"{raw}"')


def collect_quoted_values(source: str, keys: tuple[str, ...]) -> set[str]:
    key_pattern = "|".join(re.escape(key) for key in keys)
    pattern = re.compile(rf"\b(?:{key_pattern})\s*:\s*\"((?:\\.|[^\"\\])*)\"")
    values: set[str] = set()
    for match in pattern.finditer(source):
      try:
          text = normalize_text(decode_js_string(match.group(1)))
      except json.JSONDecodeError:
          continue
      if text and text != "—":
          values.add(text)
    return values


def collect_meaning_values(source: str) -> set[str]:
    meaning_match = re.search(r"\bconst\s+MEANING\s*=\s*\{(?P<body>.*?)\n\s*\};", source, re.S)
    if not meaning_match:
        return set()
    return collect_quoted_values("{" + meaning_match.group("body") + "}", ("",))


def collect_learning_english_texts() -> dict[str, set[str]]:
    source = (ROOT / "learning-english.html").read_text(encoding="utf-8")
    english = collect_quoted_values(source, ("english", "word", "phrase", "example"))
    return {"en-US": english}


def collect_citizenship_texts() -> dict[str, set[str]]:
    source = (ROOT / "citizenship-interview-prep.html").read_text(encoding="utf-8")
    english = collect_quoted_values(source, ("q", "a", "word"))
    chinese = collect_quoted_values(source, ("qZh", "aZh"))

    meaning_match = re.search(r"\bconst\s+MEANING\s*=\s*\{(?P<body>.*?)\n\s*\};", source, re.S)
    if meaning_match:
        chinese.update(
            normalize_text(decode_js_string(match.group(1)))
            for match in re.finditer(r":\s*\"((?:\\.|[^\"\\])*)\"", meaning_match.group("body"))
        )

    return {"en-US": english, "zh-CN": {text for text in chinese if text and text != "—"}}


def collect_texts() -> dict[str, set[str]]:
    texts: dict[str, set[str]] = {"en-US": set(), "zh-CN": set()}
    for lang, values in collect_learning_english_texts().items():
        texts.setdefault(lang, set()).update(values)
    for lang, values in collect_citizenship_texts().items():
        texts.setdefault(lang, set()).update(values)
    return texts


def openai_speech(api_key: str, text: str, lang: str) -> bytes:
    payload = {
        "model": MODEL,
        "voice": VOICE,
        "input": text,
        "instructions": ZH_INSTRUCTIONS if lang.lower() == "zh-cn" else EN_INSTRUCTIONS,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def generate(api_key: str, texts: dict[str, set[str]], limit: int | None, force: bool) -> None:
    generated = 0
    skipped = 0
    for lang, values in sorted(texts.items()):
        for text in sorted(values):
            path = audio_path(text, lang)
            if path.exists() and not force:
                skipped += 1
                continue
            if limit is not None and generated >= limit:
                print(f"Limit reached. Generated {generated}, skipped {skipped}.")
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Generating {path.relative_to(ROOT)} :: {text[:80]}")
            try:
                audio = openai_speech(api_key, text, lang)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")
                raise RuntimeError(f"OpenAI request failed: {exc.code} {body}") from exc
            path.write_bytes(audio)
            generated += 1
            time.sleep(0.15)
    print(f"Done. Generated {generated}, skipped {skipped}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Generate only the first N missing files.")
    parser.add_argument("--force", action="store_true", help="Regenerate files that already exist.")
    parser.add_argument("--list", action="store_true", help="List the number of files needed without generating.")
    args = parser.parse_args()

    texts = collect_texts()
    total = sum(len(values) for values in texts.values())
    missing = sum(1 for lang, values in texts.items() for text in values if not audio_path(text, lang).exists())
    print(f"Found {total} unique TTS texts; {missing} missing MP3 files.")

    if args.list:
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")
    generate(api_key, texts, args.limit, args.force)


if __name__ == "__main__":
    main()
