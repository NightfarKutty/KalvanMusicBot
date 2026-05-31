import asyncio
import random
import re
import time

import aiohttp

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROTECTION SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
RECENT_TITLES = {}

# FIX 3: Timestamp-based lock — boolean lock hangs forever after bot crash/restart.
# Store the timestamp of when lock was acquired; if > 60s old, consider it expired.
AUTO_PLAYING = {}  # chat_id -> float (timestamp) or 0

_LOCK_TTL = 60  # seconds


def _is_locked(chat_id: int) -> bool:
    ts = AUTO_PLAYING.get(chat_id, 0)
    if not ts:
        return False
    return (time.time() - ts) < _LOCK_TTL


def _acquire_lock(chat_id: int) -> bool:
    if _is_locked(chat_id):
        return False
    AUTO_PLAYING[chat_id] = time.time()
    return True


def _release_lock(chat_id: int) -> None:
    AUTO_PLAYING.pop(chat_id, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇮🇳 INDIAN LANGUAGE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANG_DB = {
    "hindi": ["hindi", "bollywood", "arijit", "jubin", "atif", "hindi song", "bollywood song"],
    "punjabi": ["punjabi", "sidhu", "diljit", "karan", "ammy", "jatt", "punjabi song"],
    "english": ["english", "ed sheeran", "taylor swift", "justin bieber", "english song"],
    "bhojpuri": ["bhojpuri", "pawan singh", "khesari", "bhojpuri song"],
    "haryanvi": ["haryanvi", "khasa", "masoom sharma", "haryanvi song"],
    "gujarati": ["gujarati", "gujju", "garba", "gujarati song"],
    "tamil": ["tamil", "tamil song", "kollywood", "anirudh", "tamil cinema"],
    "telugu": ["telugu", "telugu song", "tollywood", "devi sri", "telugu cinema"],
    "bengali": ["bengali", "bangla", "bengali song"],
    "marathi": ["marathi", "marathi song", "maharashtra"],
    "urdu": ["urdu", "urdu song", "pakistani", "nusrat"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 MOOD DATABASE (Indian Context)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOOD_DB = {
    "sad": ["sad", "broken", "heart", "bewafa", "alone", "cry", "dard", "tanha", "rula", "sad song"],
    "love": ["love", "romantic", "ishq", "pyaar", "mohabbat", "love song", "romantic song", "pyar", "ishq wala"],
    "party": ["party", "dj", "dance", "club", "bhangra", "party song", "dj song", "dance song", "masala"],
    "wedding": ["wedding", "shaadi", "marriage", "dulhan", "mehendi", "sangeet"],
    "devotional": ["devotional", "bhajan", "aarti", "mantra", "shiva", "krishna", "ram", "ganesha", "hanuman"],
    "oldschool": ["old", "classic", "90s", "80s", "kishore", "lata", "rafi", "old song", "retro", "purana"],
    "punjabi": ["punjabi", "sidhu", "diljit", "bhangra", "jatt", "punjabi song"],
    "sufi": ["sufi", "qawwali", "nusrat", "kalam", "sufiana"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 INDIAN ARTIST DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARTIST_DB = {
    "arijit singh": ["arijit", "arijit singh", "arijit song", "arijit new"],
    "atif aslam": ["atif", "atif aslam", "atif song"],
    "sidhu moosewala": ["sidhu", "sidhu moosewala", "sidhu song"],
    "diljit dosanjh": ["diljit", "diljit dosanjh", "diljit song"],
    "karan aujla": ["karan", "karan aujla", "karan song"],
    "jubin nautiyal": ["jubin", "jubin nautiyal", "jubin song"],
    "badshah": ["badshah", "badshah song", "badshah new"],
    "yo yo honey singh": ["honey singh", "yo yo", "brown rang", "yo yo honey singh"],
    "neha kakkar": ["neha kakkar", "neha song", "neha new"],
    "shreya ghoshal": ["shreya", "shreya ghoshal", "shreya song"],
    "sonu nigam": ["sonu", "sonu nigam", "sonu song"],
    "alka yagnik": ["alka", "alka yagnik", "alka song"],
    "udit narayan": ["udit", "udit narayan", "udit song"],
    "kumar sanu": ["kumar sanu", "kumar song"],
    "lata mangeshkar": ["lata", "lata mangeshkar", "lata song"],
    "kishore kumar": ["kishore", "kishore kumar", "kishore song"],
    "mohammad rafi": ["rafi", "mohammad rafi", "rafi song"],
    "ap dhillon": ["ap dhillon", "ap", "dhillon", "ap song"],
    "gurinder gill": ["gurinder gill", "gill", "gurinder song"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 INDIAN MOVIE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOVIE_DB = {
    "animal": ["animal", "animal song", "animal movie"],
    "kabir singh": ["kabir singh", "kabir movie"],
    "aashiqui 2": ["aashiqui", "aashiqui 2", "aashiqui song"],
    "shershaah": ["shershaah", "shershaah song", "shershaah movie"],
    "pushpa": ["pushpa", "pushpa song", "pushpa movie", "srivali"],
    "kgf": ["kgf", "kgf song", "rocky bhai"],
    "pathaan": ["pathaan", "pathaan song", "shah rukh"],
    "jawan": ["jawan", "jawan song", "jawan movie"],
    "dunki": ["dunki", "dunki song", "dunki movie"],
    "gadar 2": ["gadar", "gadar 2", "gadar song"],
    "rocky aur rani": ["rocky", "rani", "rocky aur rani", "kjo"],
    "tu jhoothi main makkaar": ["tu jhoothi", "tjmm", "ranbir", "shraddha"],
    "bhool bhulaiyaa 2": ["bhool bhulaiyaa", "bb2", "kartik aaryan"],
    "brahmastra": ["brahmastra", "astra", "ranbir", "alia"],
    "tanhaji": ["tanhaji", "ajay devgn", "tanhaji song"],
    "chhichhore": ["chhichhore", "sushant", "chhichhore song"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRENDING KEYWORDS (Indian)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRENDING_STYLES = [
    "hindi songs",
    "punjabi songs",
    "bollywood songs",
    "Instagram trending",
    "Love songs",
    "sad songs",
]

# FIX 1: Diverse fallback pool — random queries prevent same song every time.
# Old code used a single hardcoded query "latest bollywood hits 2025" which
# always returned the exact same #1 YouTube result.
FALLBACK_POOL = [
    "latest bollywood hits 2025",
    "top hindi songs 2025",
    "trending punjabi songs 2025",
    "popular hindi songs playlist",
    "new bollywood songs 2025",
    "best hindi songs 2024",
    "bollywood romantic hits",
    "top 10 hindi songs",
    "latest punjabi hits",
    "india trending music 2025",
    "best arijit singh songs",
    "best jubin nautiyal songs",
    "hindi love songs playlist",
    "punjabi new songs 2025",
    "bollywood party songs",
    "sad hindi songs collection",
    "old bollywood hits 90s",
    "sufi songs hindi",
    "new hindi songs march 2025",
    "hindi songs for long drive",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌍 DETECT LANGUAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_lang(title):
    if not title:
        return "hindi"
    title = title.lower()
    for lang, keys in LANG_DB.items():
        if any(x in title for x in keys):
            return lang
    return "hindi"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 DETECT MOOD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_mood(title):
    if not title:
        return "normal"
    title = title.lower()
    for mood, keys in MOOD_DB.items():
        if any(x in title for x in keys):
            return mood
    return "normal"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 DETECT ARTIST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_artist(title):
    if not title:
        return ""
    title_lower = title.lower()
    for artist, keys in ARTIST_DB.items():
        if any(x in title_lower for x in keys):
            return artist
    parts = re.split(r"[-|(]", title)
    if len(parts) > 1:
        candidate = parts[0].strip()
        if len(candidate) < 30:
            return candidate
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 DETECT MOVIE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_movie(title):
    if not title:
        return ""
    title = title.lower()
    for movie, keys in MOVIE_DB.items():
        if any(x in title for x in keys):
            return movie
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔤 TITLE NORMALIZER
# Problem: "Diwaniyat" vs "Diwaniyat - AP Dhillon" vs "Diwaniyat Lyrics"
# — different formats, same song. Two-step approach:
# Step 1: Split on " - " / " | " separators to drop artist suffix
# Step 2: Strip bracket content and noise words
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower().strip()

    for sep in [" - ", " | ", " — ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0].strip()
            break

    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", "", t)

    noise = [
        "official", "video", "music", "audio", "lyrics", "lyrical",
        "lyric", "full", "hd", "hq", "4k", "song", "new", "latest",
        "visualizer", "teaser", "promo",
    ]
    for w in noise:
        t = re.sub(rf"\b{w}\b", "", t)

    t = re.sub(r"\s+", " ", t).strip()
    return t


def _same_song(stored: str, candidate: str) -> bool:
    if not stored or not candidate:
        return False
    if len(stored) < 4 or len(candidate) < 4:
        return False
    short = stored if len(stored) <= len(candidate) else candidate
    long  = candidate if len(stored) <= len(candidate) else stored
    return long.startswith(short) or short in long


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 REPEAT CHECK (vidid + fuzzy title)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title: str = "") -> bool:
    current = time.time()

    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if current - t < 7200]
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True

    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [
                (n, t) for n, t in RECENT_TITLES[chat_id] if current - t < 7200
            ]
            for stored_norm, _ in RECENT_TITLES[chat_id]:
                if _same_song(stored_norm, norm):
                    return True

    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ➕ ADD RECENT SONG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_recent(chat_id, vidid, title: str = "") -> None:
    if not vidid:
        return
    current = time.time()

    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, current))
    if len(RECENT[chat_id]) > 50:
        RECENT[chat_id] = RECENT[chat_id][-50:]

    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm, current))
            if len(RECENT_TITLES[chat_id]) > 50:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-50:]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART QUERY BUILDER (Indian Focus)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood):
    queries = []

    clean_title = re.sub(
        r"official|video|lyrics|lyrical|hd|4k|music|song|audio|full|hq",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    queries.append(clean_title)
    queries.append(f"{clean_title} song")
    queries.append(f"{clean_title} official")
    queries.append(f"{clean_title} lyrics")

    if artist:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} hits")
        queries.append(f"{artist} best songs")
        if movie:
            queries.append(f"{artist} {movie} song")
        if lang:
            queries.append(f"{artist} {lang} songs")

    if movie:
        queries.append(f"{movie} songs")
        queries.append(f"{movie} all songs")
        queries.append(f"{movie} jukebox")
        queries.append(f"{movie} playlist")

    if mood == "sad":
        queries += ["sad hindi songs", "heartbreak songs hindi", "bewafa songs"]
    elif mood == "love":
        queries += ["romantic hindi songs", "love songs bollywood", "ishq wala song"]
    elif mood == "party":
        queries += ["party punjabi songs", "dj remix hindi", "dance songs bollywood"]
    elif mood == "wedding":
        queries += ["wedding songs hindi", "shaadi ke gane"]
    elif mood == "devotional":
        queries += ["bhajan", "aarti songs", "hanuman chalisa"]
    elif mood == "oldschool":
        queries += ["90s hindi songs", "old bollywood songs", "retro hindi songs"]
    elif mood == "sufi":
        queries += ["sufi songs hindi", "qawwali hits"]

    if lang == "hindi":
        queries += ["latest bollywood hits", "trending hindi songs 2025"]
    elif lang == "punjabi":
        queries += ["latest punjabi songs 2025", "punjabi hits"]
    elif lang == "bhojpuri":
        queries.append("bhojpuri hits")
    elif lang == "haryanvi":
        queries.append("haryanvi songs 2025")
    elif lang == "gujarati":
        queries.append("gujarati garba songs")
    elif lang == "tamil":
        queries.append("tamil hits")
    elif lang == "telugu":
        queries.append("telugu hits")
    elif lang == "bengali":
        queries.append("bengali songs")
    elif lang == "marathi":
        queries.append("marathi songs")
    elif lang == "urdu":
        queries.append("urdu songs")

    if len(queries) < 5:
        queries.extend(TRENDING_STYLES)

    bad_words = [
        "slowed", "reverb", "lofi", "8d", "live", "mix", "dj remix",
        "bass boosted", "cover", "karaoke", "instrumental", "sped up",
    ]

    final = []
    for q in queries:
        q_lower = q.lower()
        if not any(bad in q_lower for bad in bad_words):
            if q not in final and len(q) > 3:
                final.append(q)

    return final[:20]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎵 BEST SONG FINDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_best_song(chat_id, queries, last_title, last_vidid, artist, movie, mood, lang):
    candidates = []
    original_words = last_title.lower().split()

    for q in queries:
        try:
            details, vidid = await yt.track(q)
            if not vidid:
                continue

            if vidid == last_vidid:
                continue

            title = details.get("title", "").lower()
            duration = details.get("duration_min", "0:00") or "0:00"

            bad_words = [
                "slowed", "reverb", "8d", "lofi", "live", "mix", "dj remix",
                "bass boosted", "cover", "karaoke", "instrumental", "sped up",
            ]
            if any(x in title for x in bad_words):
                continue

            if title.strip() == last_title.lower().strip():
                continue

            try:
                mins = int(duration.split(":")[0])
                if mins < 2 or mins > 10:
                    continue
            except Exception:
                pass

            if await is_repeat(chat_id, vidid, details.get("title", "")):
                continue

            score = 0

            match_count = sum(1 for w in original_words[:5] if w in title and len(w) > 3)
            score += match_count * 15

            if artist and artist.lower() in title:
                score += 50
                if title.startswith(artist.lower()):
                    score += 30

            if movie and movie.lower() in title:
                score += 45

            if any(x in title for x in LANG_DB.get(lang, [])):
                score += 20

            if mood != "normal":
                mood_keywords = MOOD_DB.get(mood, [])
                if any(x in title for x in mood_keywords):
                    score += 15

            score += 50

            # FIX 2: Add small random jitter so equal-score songs don't always
            # resolve to the same top result. Without jitter, the same song
            # always wins ties since list order is deterministic per query.
            score += random.randint(0, 10)

            candidates.append((score, vidid, details))

        except Exception:
            continue

        await asyncio.sleep(0.2)

    # FIX 2: Shuffle before sort so ties are broken randomly, not by query order
    random.shuffle(candidates)
    candidates.sort(key=lambda x: x[0], reverse=True)

    if candidates:
        best = candidates[0]
        return best[1], best[2]

    return None, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 THUMBNAIL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_thumbnail_direct(video_id):
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    ]
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return url
            except Exception:
                continue
    return urls[-1]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇮🇳 INDIAN EMOJI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_indian_emoji():
    emojis = ["🇮🇳","🎧","❤️","🎶","✨","🎤","💖","🎵","🔥","💫","🎸","💕","🪩","🌙","💘","🥰","🎼","⚡","💞","🦋","🎶","💜","🎤","🌸","🕺","💃","💝","🎧","🌈","❣️","🪘","💗","✨","🔥"]
    return random.choice(emojis)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 MAIN AUTOPLAY FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# FIX 1: Fallback chain now uses is_repeat() — not just vidid == last_vidid.
#         Old code: only blocked the immediately previous song.
#         New code: blocks ANY song played in last 2 hours.
#
# FIX 2: Random jitter added to scoring + FALLBACK_POOL is shuffled.
#         Old code: same query = same #1 YouTube result = same song every time.
#         New code: random pool + jitter ensures variety even in fallbacks.
#
# FIX 3: AUTO_PLAYING uses timestamp instead of boolean.
#         Old code: bot crash/restart left lock = True → autoplay stuck forever.
#         New code: lock expires after 60s automatically.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(
    chat_id: int,
    original_chat_id: int,
    last_title: str = "",
    last_vidid: str = "",
) -> bool:
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream
    from strings import get_string

    # FIX 3: Timestamp-based lock — won't hang after bot restart
    if not _acquire_lock(chat_id):
        return False

    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False

        # Mark last played song as recent BEFORE searching
        if last_vidid:
            await add_recent(chat_id, last_vidid, last_title)

        indian_emoji = get_indian_emoji()

        try:
            msg = await app.send_message(
                original_chat_id,
                f"{indian_emoji} ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ...........",
            )
        except Exception:
            return False

        if not last_title:
            queue = db.get(chat_id)
            if queue and len(queue) > 0:
                last_title = queue[0].get("title", "latest hindi song")
            else:
                last_title = "latest hindi song"

        lang = detect_lang(last_title)
        mood = detect_mood(last_title)
        artist = extract_artist(last_title)
        movie = detect_movie(last_title)

        queries = build_smart_queries(last_title, artist, movie, lang, mood)

        vidid, details = await get_best_song(
            chat_id, queries, last_title, last_vidid, artist, movie, mood, lang
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # FIX 1: Fallback chain — use is_repeat() not just == last_vidid
        # Old code only blocked the one song that just played.
        # New code blocks any song heard in the last 2 hours.
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        if not vidid and movie:
            d, v = await yt.track(f"{movie} all songs")
            if v and not await is_repeat(chat_id, v, d.get("title", "") if d else ""):
                vidid, details = v, d

        if not vidid and artist:
            d, v = await yt.track(f"{artist} hits")
            if v and not await is_repeat(chat_id, v, d.get("title", "") if d else ""):
                vidid, details = v, d

        if not vidid and lang:
            d, v = await yt.track(f"{lang} trending songs")
            if v and not await is_repeat(chat_id, v, d.get("title", "") if d else ""):
                vidid, details = v, d

        # FIX 2: Randomized final fallback pool — shuffled so we never get
        # the same #1 YouTube result from a hardcoded query every single time.
        if not vidid:
            pool = FALLBACK_POOL.copy()
            random.shuffle(pool)
            for fallback_q in pool:
                try:
                    d, v = await yt.track(fallback_q)
                    if v and not await is_repeat(chat_id, v, d.get("title", "") if d else ""):
                        vidid, details = v, d
                        break
                except Exception:
                    continue

        if not vidid:
            try:
                await msg.edit_text("❌ ɴᴏ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
            return False

        new_title = details.get("title", "") if details else ""
        await add_recent(chat_id, vidid, new_title)

        link = f"https://youtube.com/watch?v={vidid}"

        try:
            thumb = details.get("thumb", "")
            if not thumb or not thumb.startswith("http"):
                thumb = await get_thumbnail_direct(vidid)
        except Exception:
            thumb = await get_thumbnail_direct(vidid)

        language = await get_lang(chat_id)
        _ = get_string(language)

        await stream(
            _,
            msg,
            app.id,
            {
                "link": link,
                "vidid": vidid,
                "title": details.get("title", "🇮🇳 ꜱɪᴍɪʟᴀʀ ɪɴᴅɪᴀɴ ꜱᴏɴɢ"),
                "duration_min": details.get("duration_min", "00:00"),
                "thumb": thumb,
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )

        try:
            await msg.delete()
        except Exception:
            pass

        return True

    except Exception:
        return False

    finally:
        # FIX 3: Always release the lock — even on exception or early return
        _release_lock(chat_id)
