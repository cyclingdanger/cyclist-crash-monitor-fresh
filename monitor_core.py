from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

SCAN_TIMEOUT = 4

SEARCH_QUERIES = [
    'cyclist killed vehicle crash',
    'bicyclist killed vehicle crash',
    'cyclist seriously injured crash',
    'bicyclist seriously injured crash',
    'cyclist critically injured crash',
    'bicyclist critically injured crash',
    'cyclist hospitalized vehicle crash',
    'cyclist spinal injury crash',
    'site:local10.com cyclist bicyclist cycling crash',
    'site:nbcmiami.com cyclist bicyclist bicycle crash',
    '"Rickenbacker Causeway" cyclist',
    '"Rickenbacker Causeway" bicycle',
]

DIRECT_FEEDS = [
    ("WPLG Local 10", "https://www.local10.com/rss/?nav=off"),
    ("NBC Miami", "https://www.nbcmiami.com/?rss=y"),
]

FATAL_PATTERNS = [
    r"\bkilled\b", r"\bdied\b", r"\bdead\b", r"\bfatal\b", r"\bdeath\b",
    r"\bdies\b", r"\bpronounced dead\b", r"\bdied at the scene\b",
]
SERIOUS_PATTERNS = [
    r"\bseriously injured\b", r"\bserious injuries?\b", r"\bcritically injured\b",
    r"\bcritically hurt\b", r"\bcritical condition\b", r"\bcritical injuries?\b",
    r"\blife[- ]threatening\b", r"\bhospitalized\b", r"\bspinal (?:cord )?injur(?:y|ies)\b",
    r"\bparaly[sz](?:ed|is|ation)\b", r"\bno movement\b", r"\btraumatic injuries?\b",
    r"\bmultiple injuries\b", r"\brushed to the hospital\b", r"\brushed to hospital\b",
    r"\brushed to\b", r"\brushed\b", r"\bairlifted\b", r"\bfighting for (?:his|her|their) life\b",
]
CYCLIST_RE = re.compile(r"\b(?:cyclist|bicyclist|cycling|bike rider|bicycle rider|person riding (?:a )?bicycle)\b", re.I)
VEHICLE_RE = re.compile(r"\b(?:car|vehicle|truck|suv|pickup|motorcycle|driver|motorist|van|bus|semi|tractor[- ]trailer)\b", re.I)
CRASH_RE = re.compile(r"\b(?:crash(?:ed)?|collision|struck|hit|knocked down|run over|accident|wreck|traffic incident)\b", re.I)

CITY_STATE = {
    "Miami": "Florida", "Key Biscayne": "Florida", "Virginia Key": "Florida",
    "Fort Lauderdale": "Florida", "Lauderhill": "Florida", "West Palm Beach": "Florida",
    "Palm Beach": "Florida", "Boca Raton": "Florida", "Port St. Lucie": "Florida",
    "Orlando": "Florida", "Tampa": "Florida", "Jacksonville": "Florida",
    "St. Petersburg": "Florida", "Gainesville": "Florida", "Hollywood": "Florida",
    "Austin": "Texas", "Dallas": "Texas", "Houston": "Texas", "San Antonio": "Texas",
    "Phoenix": "Arizona", "Tucson": "Arizona", "Denver": "Colorado", "Boulder": "Colorado",
    "New York City": "New York", "New York": "New York", "Buffalo": "New York",
    "Boston": "Massachusetts", "Chicago": "Illinois", "Seattle": "Washington",
    "Portland": "Oregon", "Los Angeles": "California", "San Diego": "California",
    "San Francisco": "California", "Sacramento": "California", "Las Vegas": "Nevada",
    "Charlotte": "North Carolina", "Raleigh": "North Carolina", "Atlanta": "Georgia",
    "Nashville": "Tennessee", "Memphis": "Tennessee", "New Orleans": "Louisiana",
    "Washington": "District of Columbia", "Baltimore": "Maryland", "Philadelphia": "Pennsylvania",
    "Pittsburgh": "Pennsylvania", "Columbus": "Ohio", "Cleveland": "Ohio", "Detroit": "Michigan",
    "Minneapolis": "Minnesota", "Kansas City": "Missouri", "St. Louis": "Missouri",
    "Omaha": "Nebraska", "Salt Lake City": "Utah", "Albuquerque": "New Mexico",
    "Oklahoma City": "Oklahoma", "Tulsa": "Oklahoma", "Little Rock": "Arkansas",
    "Richmond": "Virginia", "Virginia Beach": "Virginia", "Norfolk": "Virginia",
    "Louisville": "Kentucky", "Indianapolis": "Indiana", "Milwaukee": "Wisconsin",
    "Newark": "New Jersey", "Jersey City": "New Jersey", "Hartford": "Connecticut",
    "Providence": "Rhode Island", "Manchester": "New Hampshire",
}
STATE_NAMES = {"Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey","New Mexico","New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming","District of Columbia"}

KNOWN_REGRESSION = {
    "title": "Orthopedic surgeon suffers spinal injury after driver struck him while cycling on Rickenbacker Causeway in Miami",
    "summary": "A Miami orthopedic surgeon was hospitalized after a driver struck him while he was cycling on Rickenbacker Causeway in Virginia Key. Family reported a spinal cord injury and other serious injuries.",
    "url": "https://www.local10.com/traffic/2026/08/31/orthopedic-surgeon-suffers-spinal-injury-after-driver-struck-him-while-cycling-in-miamis-virginia-key/",
    "source": "WPLG Local 10", "published": "2026-08-31", "location": "Florida", "status": "Seriously Injured",
}


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(s or "").lower()).strip()


def tokens(s: str) -> set[str]:
    stop = {"the","a","an","and","of","in","on","after","by","to","for","while","from","with","his","her","their","driver","struck"}
    return {x for x in normalize(s).split() if len(x) > 2 and x not in stop}


def token_similarity(a: str, b: str) -> float:
    aa, bb = tokens(a), tokens(b)
    return len(aa & bb) / max(1, len(aa | bb)) if aa and bb else 0.0


def status_from_text(text: str) -> str | None:
    t = normalize(text)
    if any(re.search(p, t) for p in FATAL_PATTERNS): return "Killed"
    if any(re.search(p, t) for p in SERIOUS_PATTERNS): return "Seriously Injured"
    return None


def is_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}"
    return bool(CYCLIST_RE.search(text) and (VEHICLE_RE.search(text) or CRASH_RE.search(text)) and status_from_text(text))


def location_from_text(text: str) -> str:
    for city, state in sorted(CITY_STATE.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(r"\b" + re.escape(city) + r"\b", text, re.I): return state
    for state in sorted(STATE_NAMES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(state) + r"\b", text, re.I): return state
    return "Unknown"


def same_incident(a: dict, b: dict) -> bool:
    if a.get("url") == b.get("url"): return True
    if token_similarity(a.get("title", ""), b.get("title", "")) >= 0.48: return True
    if a.get("location") != b.get("location") or a.get("location") == "Unknown": return False
    common = {"cyclist","bicyclist","cycling","bike","bicycle","rider","crash","collision","struck","hit","driver","vehicle","car","injured","injury","hospital","hospitalized","serious","critical","killed","dead","fatal","surgeon","person"}
    sa = tokens(a.get("title", "") + " " + a.get("summary", "")) - common
    sb = tokens(b.get("title", "") + " " + b.get("summary", "")) - common
    return len(sa & sb) >= 3


def parse_date(value: str) -> str:
    try: return parsedate_to_datetime(value).date().isoformat()
    except Exception:
        m = re.search(r"(20\d\d)[-/](\d\d)[-/](\d\d)", value or "")
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else datetime.now(timezone.utc).date().isoformat()


def fetch_rss(url: str, label: str) -> list[dict]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 CyclistCrashMonitor/1.0"})
        with urlopen(req, timeout=SCAN_TIMEOUT) as response:
            root = ET.fromstring(response.read())
    except Exception:
        return []
    out=[]
    for item in root.findall(".//item"):
        title=(item.findtext("title") or "").strip(); link=(item.findtext("link") or "").strip()
        desc=(item.findtext("description") or "").strip(); pub=(item.findtext("pubDate") or "").strip()
        if title and link:
            out.append({"title":html.unescape(title),"summary":html.unescape(re.sub(r"<[^>]+>"," ",desc)),"url":link,"source":label,"published":parse_date(pub)})
    return out


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-US&gl=US&ceid=US:en"


def bing_news_url(query: str) -> str:
    return "https://www.bing.com/news/search?q=" + quote_plus(query) + "&format=RSS"
