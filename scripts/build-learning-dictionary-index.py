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
TRANSLATIONS_PATH = ROOT / "data" / "learning-dictionary-translations.zh-CN.json"
COMPOUND_WORDS = {
    "afternoon",
    "anyone",
    "anything",
    "cannot",
    "everyone",
    "everything",
    "inside",
    "nothing",
    "outside",
    "someone",
    "something",
    "sometimes",
    "without",
}
OPEN_COMPOUND_WORDS = {
    "air conditioner",
    "air conditioning",
    "alarm clock",
    "apple juice",
    "baby care",
    "baby food",
    "baggage claim",
    "bank account",
    "baseball bat",
    "bath towel",
    "boarding pass",
    "bookcase",
    "bus stop",
    "cell phone",
    "city hall",
    "coffee shop",
    "credit card",
    "driver's license",
    "dust storm",
    "fire alarm",
    "first aid",
    "front door",
    "green card",
    "heat wave",
    "high school",
    "ice cream",
    "id card",
    "library card",
    "living room",
    "movie theater",
    "one-way ticket",
    "parking lot",
    "phone number",
    "post office",
    "social security number",
    "street light",
    "traffic light",
    "train station",
    "video game",
    "washing machine",
}
NON_COMPOUND_PHRASES = {
    "about your health",
    "about your skills and this afternoon",
    "find your-seat",
    "get up",
    "wash dishes",
}
EXCLUDED_VOCABULARY_ENTRIES = {
    "front yard",
    "go shopping",
    "yard sale",
    "yard waste bag",
}

REF_TOKEN = r"\d{1,3}(?:[-~·.][~A-Za-z0-9]{1,3}){0,2}(?![A-Za-z0-9-])"
REF_GROUP_RE = re.compile(rf"(?<=\s)({REF_TOKEN}(?:\s*,\s*(?:{REF_TOKEN}|[A-Za-z0-9]+))*)")
REF_ONLY_RE = re.compile(rf"^{REF_TOKEN}(?:\s*,\s*(?:{REF_TOKEN}|[A-Za-z0-9]+))*$")
TRAILING_REF_COMMA_RE = re.compile(rf"{REF_TOKEN},\s*$")
PAGE_HEADER_RE = re.compile(r"^(?:Page|P:)\s*\d+\s*$", re.IGNORECASE)
INDEX_INTRO_RE = re.compile(r"^.*?(?=3-point turn\s+130-25)", re.IGNORECASE | re.DOTALL)


def load_translation_map() -> dict[str, str]:
    if not TRANSLATIONS_PATH.exists():
        return {}
    data = json.loads(TRANSLATIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{TRANSLATIONS_PATH} must contain a JSON object")
    translations = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        normalized_key = key.strip().casefold()
        translation = value.strip()
        if normalized_key and translation:
            translations[normalized_key] = translation
    return translations

MANUAL_WRAPPED_ENTRIES = [
    ("avocado", ["48-14"]),
    ("bald", ["43-35"]),
    ("cardiologist", ["96-1"]),
    ("child", ["42-3"]),
    ("country", ["20-15"]),
    ("couch", ["21-20"]),
    ("desk", ["4-4", "120-1"]),
    ("e-mail", ["108-19"]),
    ("enter your PIN number", ["81-23"]),
    ("face", ["9-6", "86-4"]),
    ("face powder", ["99-42"]),
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
    ("air conditioning", ["127-67"]),
    ("air pump", ["126-41"]),
    ("appliance repairperson", ["30-E"]),
    ("bakery", ["36-1"]),
    ("balance the checkbook", ["81-16"]),
    ("bacon, lettuce, and tomato sandwich", ["61-27"]),
    ("bank officer", ["80-13"]),
    ("bottle-return machine", ["55-25"]),
    ("bread-and-butter plate", ["63-24"]),
    ("bring in your homework", ["6-22"]),
    ("bird watching", ["135-N"]),
    ("central processing unit", ["78-2"]),
    ("call button", ["97-5"]),
    ("cash a traveler's check", ["80-D"]),
    ("checkbook", ["81-16", "81-19"]),
    ("catcher's mask", ["143-5"]),
    ("change-of-address form", ["82-15"]),
    ("change the baby's diaper", ["100-8"]),
    ("brussels sprout", ["49-21"]),
    ("bubble the answer", ["7-54"]),
    ("chicken wings", ["50-18", "64-4"]),
    ("Children's Clothing Department", ["74-9"]),
    ("clogged", ["30-2"]),
    ("child day-care worker", ["112-17"]),
    ("certified mail", ["82-9"]),
    ("customs and immigration", ["131-E"]),
    ("customs declaration form", ["131-24", "161-13"]),
    ("drive-through window", ["131-22", "161-3"]),
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
    ("Good-bye", ["12-9"]),
    ("environmental problems", ["158"]),
    ("Fahrenheit", ["14-20"]),
    ("find your seat", ["132-J"]),
    ("get some information about", ["75-F"]),
    ("go to an Internet cafe", ["163-15"]),
    ("gospel music", ["148-7"]),
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
    ("identification number", ["81-23"]),
    ("ice cream truck", ["41-28"]),
    ("man", ["42-8"]),
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
    ("long-sleeved shirt", ["71-1"]),
    ("make breakfast", ["9-15"]),
    ("Furniture Department", ["74-11"]),
    ("Home Furnishings Department", ["74-11"]),
    ("hand-held video game", ["76-35"]),
    ("helmet", ["123-1", "139-19", "140-9"]),
    ("handicapped-accessible room", ["162-4"]),
    ("help each other", ["6-28"]),
    ("handicapped parking only", ["130-16"]),
    ("health-care attendant", ["113-35"]),
    ("homemaker", ["113-37"]),
    ("horseback riding", ["140-H"]),
    ("hand in your homework", ["6-25"]),
    ("hearing impaired", ["42-23"]),
    ("heating and air conditioning service", ["31-L"]),
    ("horror movie", ["149-26"]),
    ("put your bag on the conveyor belt", ["132-C"]),
    ("put your computer in a tray", ["132-D"]),
    ("read a book", ["11-4"]),
    ("read the newspaper", ["11-5"]),
    ("repair", ["72-25", "117-22"]),
    ("stow your carry-on bag", ["132-1"]),
    ("soft", ["44-39"]),
    ("video cassette recorder", ["21-9"]),
    ("this afternoon", ["19-13"]),
    ("take the bus to school", ["10-12"]),
    ("thank-you note", ["108-17"]),
    ("third floor", ["28-16"]),
    ("talk about your skills and qualifications", ["118-H"]),
    ("vacuum cleaner attachments", ["32-6"]),
    ("waiter", ["62-12", "115-36"]),
    ("watering can", ["35-13"]),
    ("water the flowers", ["35-O"]),
    ("wash the dishes", ["10-2"]),
    ("water pollution", ["158-14"]),
    ("witch", ["45"]),
    ("write a thank-you note", ["118-L"]),
    ("window cleaner", ["32-13"]),
    ("word-processing program", ["78-19"]),
    ("zoom lens", ["77-17"]),
    ("shipping department", ["121-17"]),
    ("seat the customers", ["62-A"]),
    ("woman", ["42-9"]),
]

CORRECTED_ENTRY_TEXT = {
    "antibiotic ointrnent": "antibiotic ointment",
    "arithrnetic": "arithmetic",
    "burnper": "bumper",
    "cake rnix": "cake mix",
    "clarns": "clams",
    "cuy souvenirs": "buy souvenirs",
    "departrnent": "Department",
    "dol! house furniture": "doll house furniture",
    "ernbroidery": "embroidery",
    "inforrnation": "information",
    "intercorn": "intercom",
    "iurnber": "lumber",
    "musical cornedy": "musical comedy",
    "new rnoon": "new moon",
    "rnarried": "married",
    "rnushroom": "mushroom",
    "transrnission": "transmission",
    "urnbrella": "umbrella",
    "vacuurn cleaner bag": "vacuum cleaner bag",
    "yesterdayafternoon": "yesterday afternoon",
    "rnusic club": "music club",
    "srnoke detector": "smoke detector",
    "srnall": "small",
    "oepartment": "Department",
    "tabla": "table",
    "third [loor": "third floor",
}

CORRECTED_ENTRY_REFS = {
    "air conditioning": {
        "remove": {"31-apple"},
    },
    "concert": {
        "remove": {"147-couch", "21-20"},
    },
}

CORRECTED_MALFORMED_ENTRIES = {
    "avocado 48--14 bald",
    "about your skills and this afternoon",
    "appliance repairperson bakery",
    "b repair",
    "balance the checkbook air pump",
    "Can you please repeat Okay.",
    "central processing unit chicken wings",
    "call button 97-?",
    "cash a traveler's check checkbook",
    "catcher's mas k",
    "change-of-address bubble the answer",
    "change the baby's brussels sprout",
    "child 42-' cardiologist",
    "child day-care worker certified mail",
    "Children's Clothing dogged",
    "concrete mixer truck country rnusic",
    "customer service desk",
    "e-rnail",
    "enter your P1Nnumber face powder",
    "environmental Fahrenheit",
    "find your-seat",
    "get some information gospel music",
    "Good-bye.",
    "hand In your homework hearing impaired",
    "hand-held video game helmet",
    "handicapped-accessible help each other",
    "handicapped parking hen",
    "health-care attendant homemaker",
    "heating and air conditioning horror movie",
    "bottle-return machine bank officer",
    "Furniture Oepartment get up",
    "go to an Internet Hour",
    "Home Furnishings ice cream truck",
    "identification number face",
    "I like your city very water pollution",
    "l'rn from ....",
    "I'm here for five days. woman",
    "long-sleeved shirt 71-'",
    "l'd like a wake-up call water the flowers",
    "luggage compartment man",
    "make breakfast 9-'",
    "customs declaration detour",
    "drive-through window customs",
    "put your bag on the read a book",
    "put your computer in a read the newspaper",
    "science fiction movie sand",
    "shipping department seat the customers",
    "vacuum cleaner waiter",
    "video cassette recorder wash the dishes",
}


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
VOWEL_TEAMS = (
    "ai",
    "air",
    "are",
    "ay",
    "ea",
    "ear",
    "ee",
    "eer",
    "ei",
    "ere",
    "ey",
    "ie",
    "igh",
    "ire",
    "oa",
    "oe",
    "oi",
    "oo",
    "oor",
    "ore",
    "ou",
    "our",
    "ow",
    "oy",
    "ue",
    "ui",
    "ure",
)
VOWEL_TEAM_MATCH_ORDER = sorted(VOWEL_TEAMS, key=len, reverse=True)


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
LEAKED_REFERENCE_FRAGMENT_RE = re.compile(r"\b\d{1,3}-['’](?:\s+.*)?$")


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
    if LEAKED_REFERENCE_FRAGMENT_RE.search(text):
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


def is_plain_single_word(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]+", text.strip()))


def is_phrase_like_vocabulary_entry(normalized: str) -> bool:
    if not normalized:
        return True
    if re.search(r'[?!:;"]', normalized):
        return True
    if re.search(r"\b(about your|and this|find your|with a|with an|to the|of the|for a|for an|please|can you|i'm|i'd|don't|what's)\b", normalized):
        return True
    words = [word for word in normalized.split(" ") if word]
    return len(words) > 3


def is_vocabulary_compound(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().casefold())
    if normalized in NON_COMPOUND_PHRASES:
        return False
    if normalized in COMPOUND_WORDS or normalized in OPEN_COMPOUND_WORDS:
        return True
    if is_phrase_like_vocabulary_entry(normalized):
        return False
    return "-" in normalized


def get_prefix(text: str) -> str:
    if not is_plain_single_word(text):
        return "none"
    normalized = re.sub(r"[^a-z]", "", text.lower())
    return next((prefix for prefix in PREFIXES if normalized.startswith(prefix) and len(normalized) > len(prefix) + 2), "none")


def get_suffix(text: str) -> str:
    if not is_plain_single_word(text):
        return "none"
    normalized = re.sub(r"[^a-z]", "", text.lower())
    return next((suffix for suffix in SUFFIXES if normalized.endswith(suffix) and len(normalized) > len(suffix) + 2), "none")


def get_syllable_type(text: str) -> str:
    normalized = re.sub(r"[^a-z]", "", text.lower())
    if not normalized:
        return ""
    if normalized.endswith("e") and len(normalized) > 2:
        return "silent-e"
    if get_vowel_teams(text):
        return "vowel-team"
    return "closed" if re.search(r"[aeiou][^aeiou]$", normalized) else "open"


def get_vowel_teams(text: str) -> list[str]:
    normalized = re.sub(r"[^a-z]", "", text.lower())
    if not normalized:
        return []
    teams = set(re.findall("|".join(VOWEL_TEAM_MATCH_ORDER), normalized))
    return [team for team in VOWEL_TEAMS if team in teams]


def build_entries(raw_text: str) -> tuple[list[dict], dict]:
    translations = load_translation_map()
    parsed: list[ParsedEntry] = []
    report = {
        "unparsedLines": [],
        "wrappedLines": [],
        "duplicateEntries": [],
        "suspiciousRefs": [],
        "discardedMalformedEntries": [],
        "missingIpa": [],
        "missingChineseSample": [],
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
        if normalized_text in CORRECTED_MALFORMED_ENTRIES:
            report["discardedMalformedEntries"].append({"line": entry.line, "text": normalized_text, "refs": entry.refs, "reason": "replaced by manual correction"})
            continue
        if normalized_text.casefold() in EXCLUDED_VOCABULARY_ENTRIES:
            report.setdefault("discardedNonWordEntries", []).append({"line": entry.line, "text": normalized_text, "refs": entry.refs})
            continue
        if is_malformed_entry_text(normalized_text):
            report["discardedMalformedEntries"].append({"line": entry.line, "text": normalized_text, "refs": entry.refs})
            continue
        corrected_text = CORRECTED_ENTRY_TEXT.get(normalized_text.casefold())
        if corrected_text:
            report.setdefault("correctedEntryText", []).append({"line": entry.line, "to": corrected_text, "refs": entry.refs})
            normalized_text = corrected_text
        corrected_refs = CORRECTED_ENTRY_REFS.get(normalized_text.casefold())
        if corrected_refs:
            remove_refs = corrected_refs.get("remove", set())
            removed = [ref for ref in entry.refs if ref in remove_refs]
            if removed:
                entry.refs = [ref for ref in entry.refs if ref not in remove_refs]
                report.setdefault("correctedEntryRefs", []).append({"line": entry.line, "text": normalized_text, "removedCount": len(removed)})
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
        chinese = translations.get(normalized, "")
        if not chinese and len(report["missingChineseSample"]) < 100:
            report["missingChineseSample"].append(entry.text)
        word = {
            "id": f"index-{index:04d}-{re.sub(r'[^a-z0-9]+', '-', normalized).strip('-') or 'entry'}",
            "type": "word",
            "text": entry.text,
            "word": entry.text,
            "chinese": chinese,
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
            "vowelTeams": get_vowel_teams(entry.text),
            "compound": is_vocabulary_compound(entry.text),
        }
        report["missingIpa"].append(entry.text)
        entries.append(word)

    counts = Counter(entry["theme"] for entry in entries)
    report["summary"] = {
        "rawLines": len(raw_text.splitlines()),
        "parsedEntries": len(parsed),
        "uniqueEntries": len(entries),
        "translatedEntries": sum(1 for entry in entries if entry["chinese"]),
        "missingChinese": sum(1 for entry in entries if not entry["chinese"]),
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
