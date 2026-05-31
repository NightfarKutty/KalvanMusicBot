"""
autoplay.py — VishalMusic Autoplay System
==========================================

Search method: py_yt.VideosSearch (limit=10)
  - Already installed and used throughout this bot (Youtube.py)
  - Returns 10 results per query → plenty of options to filter
  - Works reliably with the Shruti API download system

Download: unchanged — stream() → YouTube.download() → Shruti API (same as normal play)

Filters applied to every candidate:
  • Duration: 1:30 – 8:00 min (no shorts, no 2-3 hour albums/podcasts)
  • No karaoke / live concert / jukebox / instrumental / mashup / slowed etc.
  • Same language as current song (Hindi→Hindi, Punjabi→Punjabi, Tamil→Tamil)
  • Not played in the last 2 hours (per-chat RECENT history)
"""

import asyncio
import random
import re
import time
from typing import Dict, List, Optional, Tuple

import aiohttp
from py_yt import VideosSearch

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt           = YouTubeAPI()
_autoplay_db = mongodb.autoplay


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔒  LOCK — prevents double-play if StreamEnded fires twice
#     Timestamp-based: never hangs after a bot crash/restart.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_LOCK: Dict[int, float] = {}
_LOCK_TTL = 60  # seconds


def _lock_acquire(chat_id: int) -> bool:
    ts = _LOCK.get(chat_id, 0)
    if ts and (time.time() - ts) < _LOCK_TTL:
        return False
    _LOCK[chat_id] = time.time()
    return True


def _lock_release(chat_id: int) -> None:
    _LOCK.pop(chat_id, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🕒  RECENT HISTORY — per-chat, 2-hour window
#     Same song never repeats within 2 hours.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_RECENT: Dict[int, Dict[str, float]] = {}
_RECENT_TTL = 7200  # 2 hours


def _mark_recent(chat_id: int, vidid: str) -> None:
    now    = time.time()
    bucket = _RECENT.setdefault(chat_id, {})
    # Prune expired entries
    _RECENT[chat_id] = {v: t for v, t in bucket.items() if now - t < _RECENT_TTL}
    _RECENT[chat_id][vidid] = now


def _is_recent(chat_id: int, vidid: str) -> bool:
    ts = _RECENT.get(chat_id, {}).get(vidid, 0)
    return bool(ts) and (time.time() - ts) < _RECENT_TTL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏱  DURATION FILTER
#     VideosSearch returns duration as a string: "3:45" or "1:02:30"
#     We accept: 1:30 min (90s) to 8:00 min (480s)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MIN_SEC = 90
_MAX_SEC = 480


def _parse_dur(dur_str: str) -> int:
    """'3:45' → 225, '1:02:30' → 3750, bad string → 0"""
    try:
        parts = [int(p) for p in str(dur_str).strip().split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        pass
    return 0


def _dur_ok(dur_str: str) -> bool:
    sec = _parse_dur(dur_str)
    if sec == 0:
        return True   # duration unknown → don't reject; let it through
    return _MIN_SEC <= sec <= _MAX_SEC


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚫  BAD-CONTENT KEYWORDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_BAD = {
    "slowed", "reverb", "8d audio", "lofi", "lo-fi", "lo fi",
    "live concert", "live performance", "live at ", "live show",
    "karaoke", "instrumental", "bass boosted", "sped up", "nightcore",
    "cover by", "reaction", "interview", "behind the scenes",
    "#shorts", "podcast", "lecture", "full album", "full movie",
    "jukebox", "mashup", "medley", "nonstop", "non stop",
    "2 hours", "3 hours", "4 hours",
}


def _title_ok(title: str) -> bool:
    t = title.lower()
    return not any(b in t for b in _BAD)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌐  LANGUAGE DETECTION
#     Step 1: Unicode script ranges (Devanagari / Gurmukhi / Tamil / Telugu …)
#     Step 2: Known artist/keyword hints in Roman script
#     Step 3: Pure-Latin with no Indian hints → English
#     Default: "hindi"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_RE_DEVA    = re.compile(r"[\u0900-\u097F]")
_RE_GURM    = re.compile(r"[\u0A00-\u0A7F]")
_RE_TAMIL   = re.compile(r"[\u0B80-\u0BFF]")
_RE_TELUGU  = re.compile(r"[\u0C00-\u0C7F]")
_RE_BENGALI = re.compile(r"[\u0980-\u09FF]")
_RE_LATIN   = re.compile(r"^[A-Za-z0-9 .,'\-!&()\[\]]+$")

_KW: List[Tuple[str, List[str]]] = [
    ("punjabi",  ["punjabi", "sidhu moosewala", "diljit", "karan aujla",
                  "ammy virk", "ap dhillon", "bhangra", "jatt", "babbu maan",
                  "gurnam bhullar", "satinder sartaaj"]),
    ("haryanvi", ["haryanvi", "khasa aala chahar", "masoom sharma", "renuka panwar"]),
    ("bhojpuri", ["bhojpuri", "pawan singh", "khesari lal", "nirahua"]),
    ("hindi",    ["hindi", "bollywood", "arijit singh", "jubin nautiyal",
                  "atif aslam", "neha kakkar", "shreya ghoshal", "sonu nigam",
                  "kishore kumar", "lata mangeshkar", "badshah",
                  "yo yo honey singh", "b praak", "darshan raval",
                  "armaan malik", "vishal mishra", "shankar mahadevan"]),
    ("tamil",    ["tamil", "kollywood", "anirudh", "sid sriram", "harris jayaraj"]),
    ("telugu",   ["telugu", "tollywood", "devi sri prasad", "thaman s"]),
    ("bengali",  ["bengali", "bangla"]),
]

_INDIAN = {"hindi", "punjabi", "haryanvi", "bhojpuri", "urdu"}


def _detect_lang(title: str) -> str:
    if _RE_DEVA.search(title):    return "hindi"
    if _RE_GURM.search(title):    return "punjabi"
    if _RE_TAMIL.search(title):   return "tamil"
    if _RE_TELUGU.search(title):  return "telugu"
    if _RE_BENGALI.search(title): return "bengali"
    tl = title.lower()
    for lang, kws in _KW:
        if any(k in tl for k in kws):
            return lang
    if _RE_LATIN.match(title.strip()):
        return "english"
    return "hindi"


def _lang_ok(candidate: str, want: str) -> bool:
    if not candidate.strip():
        return True          # unknown → allow
    got = _detect_lang(candidate)
    if got == want:
        return True
    if want in _INDIAN and got in _INDIAN:
        return True          # Hindi ↔ Punjabi ↔ Haryanvi mix is natural
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔍  VIDEO SEARCH via py_yt.VideosSearch
#     Same library already used in this bot's Youtube.py.
#     limit=10 → 10 candidates per query → plenty to filter.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _search(query: str, limit: int = 10) -> List[dict]:
    """
    Returns up to `limit` result dicts from py_yt.VideosSearch.
    Each dict has at least: id, title, duration (str "M:SS"), isLive (bool).
    Returns [] on any failure.
    """
    try:
        data = await asyncio.wait_for(
            VideosSearch(query, limit=limit).next(),
            timeout=15,
        )
        return data.get("result") or []
    except Exception:
        return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🏗  QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_NOISE_RE = re.compile(
    r"\b(official|video|lyrics|lyrical|audio|full|hd|hq|4k|"
    r"song|music|new|latest|visualizer|teaser|promo)\b",
    re.IGNORECASE,
)

_ARTIST_MAP = {
    "arijit":       "arijit singh",
    "jubin":        "jubin nautiyal",
    "atif":         "atif aslam",
    "sidhu":        "sidhu moosewala",
    "diljit":       "diljit dosanjh",
    "karan aujla":  "karan aujla",
    "ammy":         "ammy virk",
    "badshah":      "badshah",
    "neha":         "neha kakkar",
    "shreya":       "shreya ghoshal",
    "honey singh":  "yo yo honey singh",
    "ap dhillon":   "ap dhillon",
    "b praak":      "b praak",
    "darshan":      "darshan raval",
    "armaan":       "armaan malik",
    "anirudh":      "anirudh ravichander",
    "vishal":       "vishal mishra",
}

_POOL: Dict[str, List[str]] = {
    "hindi": [
        "trending hindi songs 2024",
        "latest bollywood hits",
        "best arijit singh songs",
        "best jubin nautiyal songs",
        "hindi love songs",
        "bollywood party songs",
        "sad hindi songs",
        "atif aslam hindi songs",
        "new bollywood songs",
        "hit hindi songs",
        "popular bollywood songs",
        "romantic hindi songs",
    ],
    "punjabi": [
        "trending punjabi songs 2024",
        "diljit dosanjh best songs",
        "karan aujla songs",
        "new punjabi songs",
        "punjabi love songs",
        "ap dhillon songs",
        "top punjabi songs",
        "ammy virk songs",
    ],
    "english": [
        "trending english pop songs 2024",
        "top english hits",
        "popular english songs",
        "best pop songs 2024",
        "new english songs",
        "top billboard songs",
    ],
    "tamil": [
        "trending tamil songs 2024",
        "anirudh ravichander songs",
        "new kollywood songs",
        "best tamil songs",
        "sid sriram songs",
    ],
    "telugu": [
        "trending telugu songs 2024",
        "tollywood hits 2024",
        "new telugu songs",
        "best telugu songs",
    ],
    "bhojpuri": [
        "trending bhojpuri songs",
        "pawan singh songs",
        "khesari lal songs",
        "bhojpuri hits",
    ],
    "haryanvi": [
        "trending haryanvi songs",
        "khasa aala chahar songs",
        "haryanvi hits",
    ],
    "bengali": [
        "trending bengali songs",
        "bangla hits",
        "popular bengali songs",
    ],
}


def _clean(title: str) -> str:
    t = _NOISE_RE.sub("", title)
    for sep in (" - ", " | ", " — ", " ft.", " feat.", " Ft."):
        if sep in t:
            t = t.split(sep)[0]
            break
    t = re.sub(r"[\(\[\{][^\)\]\}]{0,60}[\)\]\}]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _artist(title: str) -> str:
    tl = title.lower()
    for key, full in _ARTIST_MAP.items():
        if key in tl:
            return full
    return ""


def _queries(title: str, lang: str) -> List[str]:
    clean  = _clean(title)
    ar     = _artist(title)
    pool   = _POOL.get(lang, _POOL["hindi"]).copy()
    random.shuffle(pool)   # vary the generic pool each session

    qs: List[str] = []
    if ar:
        qs.append(f"{ar} best songs")
        qs.append(f"{ar} popular songs")
    if clean and len(clean) > 3:
        qs.append(f"songs like {clean[:45]}")
    qs.extend(pool)
    return qs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯  CANDIDATE PICKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _pick(
    results: List[dict],
    chat_id: int,
    last_vidid: str,
    want_lang: str,
    strict_lang: bool = True,
) -> Optional[str]:
    """Return the first video ID from results that passes all filters."""
    for r in results:
        vid = r.get("id", "")
        if not vid:
            continue
        if vid == last_vidid:
            continue
        if _is_recent(chat_id, vid):
            continue
        if r.get("isLive"):
            continue

        title = r.get("title") or ""
        if not _title_ok(title):
            continue

        dur = r.get("duration") or ""
        if not _dur_ok(dur):
            continue

        if strict_lang and title and not _lang_ok(title, want_lang):
            continue

        return vid
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔎  ORCHESTRATOR — runs queries until a song is found
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _find_next(
    chat_id: int,
    title: str,
    last_vidid: str,
    lang: str,
) -> Optional[str]:
    """
    Try each query with 10 results.
    Pass 1: language enforced.
    Pass 2: language relaxed (so autoplay never goes completely silent).
    """
    qs = _queries(title, lang)

    # Pass 1 — same language required
    for q in qs:
        results = await _search(q, limit=10)
        if not results:
            continue
        vid = _pick(results, chat_id, last_vidid, lang, strict_lang=True)
        if vid:
            return vid

    # Pass 2 — any language (last resort, better than nothing)
    for q in qs[:5]:
        results = await _search(q, limit=10)
        if not results:
            continue
        vid = _pick(results, chat_id, last_vidid, lang, strict_lang=False)
        if vid:
            return vid

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼  THUMBNAIL HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _thumb(vidid: str, preferred: str = "") -> str:
    if preferred and preferred.startswith("http"):
        return preferred
    for url in [
        f"https://img.youtube.com/vi/{vidid}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/mqdefault.jpg",
    ]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        return url
        except Exception:
            continue
    return f"https://img.youtube.com/vi/{vidid}/mqdefault.jpg"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀  MAIN ENTRY POINT — called from call.py → play()
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_EMOJIS = [
    "🇮🇳","🎧","❤️","🎶","✨","🎤","💖","🎵","🔥","💫",
    "🎸","💕","🪩","🌙","💘","🥰","🎼","⚡","💞","🦋",
    "💜","🌸","🕺","💃","💝","🌈","❣️","🪘","💗","🎹",
]


async def auto_play_next(
    chat_id: int,
    original_chat_id: int,
    last_title: str = "",
    last_vidid: str = "",
) -> bool:
    """
    Play the next song when the queue empties and autoplay is ON.
    Returns True if a new song started, False otherwise.
    """
    from strings import get_string
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream

    # ── Prevent double-trigger ───────────────────────────────────────────────
    if not _lock_acquire(chat_id):
        return False

    try:
        # ── Autoplay ON? ─────────────────────────────────────────────────────
        data = await _autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False

        # ── Mark finished song in history BEFORE searching ───────────────────
        if last_vidid:
            _mark_recent(chat_id, last_vidid)

        # ── "Searching…" notice ──────────────────────────────────────────────
        try:
            notice = await app.send_message(
                original_chat_id,
                f"{random.choice(_EMOJIS)} ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ...",
            )
        except Exception:
            return False

        # ── Resolve title ────────────────────────────────────────────────────
        if not last_title:
            q = db.get(chat_id)
            last_title = (q[0].get("title", "") if q else "") or "trending hindi songs"

        # ── Detect language of the song that just ended ──────────────────────
        song_lang = _detect_lang(last_title)

        # ── Find next song ───────────────────────────────────────────────────
        next_vid = await _find_next(chat_id, last_title, last_vidid, song_lang)

        if not next_vid:
            try:
                await notice.edit_text("❌ ᴀᴜᴛᴏᴘʟᴀʏ: ɴᴏ ꜱᴜɪᴛᴀʙʟᴇ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
            return False

        # ── Mark it as recent so it doesn't repeat next time ────────────────
        _mark_recent(chat_id, next_vid)

        # ── Fetch full metadata via yt.track() ───────────────────────────────
        yt_url = f"https://www.youtube.com/watch?v={next_vid}"
        try:
            details, _ = await yt.track(yt_url)
            details["vidid"] = next_vid
        except Exception:
            # Minimal fallback — stream() will still work with basic info
            details = {
                "title":        "🎵 ᴀᴜᴛᴏᴘʟᴀʏ ꜱᴏɴɢ",
                "link":         yt_url,
                "vidid":        next_vid,
                "duration_min": "0:00",
                "thumb":        "",
            }

        details["thumb"] = await _thumb(next_vid, details.get("thumb", ""))

        # ── Call stream() — downloads via Shruti API (same as normal play) ───
        language = await get_lang(chat_id)
        _  = get_string(language)

        await stream(
            _,
            notice,
            app.id,
            {
                "link":         f"https://youtube.com/watch?v={next_vid}",
                "vidid":        next_vid,
                "title":        details.get("title") or "🎵 ᴀᴜᴛᴏᴘʟᴀʏ ꜱᴏɴɢ",
                "duration_min": details.get("duration_min") or "0:00",
                "thumb":        details.get("thumb") or "",
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )

        try:
            await notice.delete()
        except Exception:
            pass

        return True

    except Exception:
        return False

    finally:
        _lock_release(chat_id)
