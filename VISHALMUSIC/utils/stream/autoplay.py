import asyncio
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
#  SYSTEM STORAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
RECENT_TITLES = {}
AUTO_PLAYING = {}
LAST_SONG_CONTEXT = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SUPER STRONG SONG FINGERPRINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_song_fingerprint(title):
    """Create unique fingerprint - removes artist, noise, everything"""
    if not title:
        return ""
    
    t = title.lower()
    
    # Remove common artist names
    artists = ["arijit", "atif", "sidhu", "diljit", "ap dhillon", "shreya", "jubin", "badshah", 
               "honey singh", "neha kakkar", "karan aujla", "gurinder gill", "yo yo", "king", 
               "mc stan", "divine", "raftaar", "sonu nigam", "alka yagnik", "kumar sanu", 
               "lata mangeshkar", "kishore kumar", "mohammad rafi", "udit narayan"]
    for a in artists:
        t = t.replace(a, "")
    
    # Remove separators
    for sep in [" - ", " | ", " — ", " ft ", " feat ", "(", ")", "[", "]", "{", "}", ".", ",", "!", "?"]:
        t = t.replace(sep, " ")
    
    # Remove noise words
    noise = ["official", "video", "music", "audio", "lyrics", "lyrical", "lyric", "full", "hd", 
             "hq", "4k", "8k", "song", "new", "latest", "remix", "cover", "reaction", "visualizer", 
             "teaser", "promo", "slowed", "reverb", "lofi", "sped", "up", "version", "original", 
             "mix", "dj", "explicit", "clean", "with", "the", "and", "for", "of", "to", "in", 
             "at", "by", "from", "movie", "film", "album", "video", "song", "hindi", "punjabi", 
             "bollywood", "tamil", "telugu", "top", "best", "hits", "jukebox", "playlist"]
    
    for w in noise:
        t = re.sub(rf'\b{w}\b', ' ', t)
    
    # Remove numbers
    t = re.sub(r'\d+', ' ', t)
    
    # Remove all special characters
    t = re.sub(r'[^a-z\s]', ' ', t)
    
    # Remove extra spaces
    t = re.sub(r'\s+', ' ', t).strip()
    
    # Take first 3-4 words only (core song name)
    words = t.split()
    if len(words) > 4:
        words = words[:4]
    
    return " ".join(words)


def is_same_song(title1, title2):
    """Check if two titles are the same song"""
    if not title1 or not title2:
        return False
    
    fp1 = get_song_fingerprint(title1)
    fp2 = get_song_fingerprint(title2)
    
    if not fp1 or not fp2:
        return False
    
    # Exact fingerprint match
    if fp1 == fp2:
        return True
    
    # One contains the other
    if fp1 in fp2 or fp2 in fp1:
        return True
    
    # Word overlap (70%+)
    words1 = set(fp1.split())
    words2 = set(fp2.split())
    
    if words1 and words2:
        common = len(words1 & words2)
        total = max(len(words1), len(words2))
        if common / total >= 0.7:
            return True
    
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DYNAMIC EXTRACTORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_core_words(title):
    if not title:
        return []
    t = title.lower()
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\[[^\]]*\]", "", t)
    for sep in [" - ", " | ", " — ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0]
            break
    words = re.findall(r"[a-z]+", t)
    noise = ["the", "and", "for", "with", "official", "video", "lyrics", "hd", "4k", "song", "new", "latest"]
    result = [w for w in words if len(w) > 3 and w not in noise]
    return result[:5]

def extract_artist(title):
    if not title:
        return ""
    t = title.strip()
    for sep in [" - ", " | ", " — ", " ft. ", " feat. ", " (", " ["]:
        if sep in t:
            candidate = t.split(sep)[0].strip()
            candidate = re.sub(r"(official|video|lyrics|hd|4k|song)$", "", candidate, flags=re.I)
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if 2 < len(candidate) < 40:
                return candidate
    words = t.split()
    if len(words) > 2:
        candidate = " ".join(words[:3])
        if len(candidate) < 35:
            return candidate
    return ""

def extract_movie(title):
    if not title:
        return ""
    t = title.lower()
    patterns = [r'from\s+([a-z0-9\s]+?)(?:\s+[a-z]+)?$', r'movie\s+([a-z0-9\s]+?)$']
    for pattern in patterns:
        match = re.search(pattern, t)
        if match:
            candidate = match.group(1).strip()
            if 2 < len(candidate) < 35:
                return candidate
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REPEAT PROTECTION (72 HOURS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title=""):
    now = time.time()
    MEMORY_TIME = 259200  # 72 hours (3 days)
    
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if now - t < MEMORY_TIME]
    
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True
    
    if title:
        fingerprint = get_song_fingerprint(title)
        if fingerprint and len(fingerprint) > 2:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [(f, t) for f, t in RECENT_TITLES[chat_id] if now - t < MEMORY_TIME]
            for stored_fp, _ in RECENT_TITLES[chat_id]:
                if fingerprint == stored_fp or fingerprint in stored_fp or stored_fp in fingerprint:
                    return True
    return False

async def add_recent(chat_id, vidid, title=""):
    if not vidid:
        return
    now = time.time()
    MEMORY_TIME = 259200
    MAX_HISTORY = 500
    
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, now))
    if len(RECENT[chat_id]) > MAX_HISTORY:
        RECENT[chat_id] = RECENT[chat_id][-MAX_HISTORY:]
    
    if title:
        fingerprint = get_song_fingerprint(title)
        if fingerprint and len(fingerprint) > 2:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((fingerprint, now))
            if len(RECENT_TITLES[chat_id]) > MAX_HISTORY:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-MAX_HISTORY:]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTEXT MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_context(chat_id, title, vidid, duration):
    LAST_SONG_CONTEXT[chat_id] = {
        "title": title,
        "vidid": vidid,
        "duration": duration,
        "artist": extract_artist(title),
        "movie": extract_movie(title),
        "fingerprint": get_song_fingerprint(title),
        "core_words": extract_core_words(title),
        "timestamp": time.time()
    }
    try:
        await mongodb.song_context.update_one({"chat_id": chat_id}, {"$set": LAST_SONG_CONTEXT[chat_id]}, upsert=True)
    except:
        pass

async def get_context(chat_id):
    if chat_id in LAST_SONG_CONTEXT:
        return LAST_SONG_CONTEXT[chat_id]
    try:
        data = await mongodb.song_context.find_one({"chat_id": chat_id})
        if data:
            del data["_id"]
            LAST_SONG_CONTEXT[chat_id] = data
            return data
    except:
        pass
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_queries(context):
    queries = []
    title = context.get("title", "")
    artist = context.get("artist", "")
    movie = context.get("movie", "")
    core_words = context.get("core_words", [])
    
    clean = get_song_fingerprint(title)
    if clean and len(clean) > 3:
        queries.append(clean)
    
    if artist and len(artist) > 2:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} new")
    
    if movie and len(movie) > 2:
        queries.append(f"{movie} songs")
    
    if artist and movie:
        queries.insert(0, f"{artist} {movie} song")
    
    if len(core_words) >= 2:
        queries.append(" ".join(core_words[:3]))
    
    queries.append("popular songs")
    queries.append("trending music")
    
    bad = ["slowed", "reverb", "lofi", "live", "cover", "remix", "top", "hits", "jukebox", "playlist", "best of"]
    seen = set()
    final = []
    for q in queries:
        if not any(b in q.lower() for b in bad):
            if q not in seen and 3 < len(q) < 60:
                seen.add(q)
                final.append(q)
    return final[:12]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SCORING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_score(new_title, context):
    if not context:
        return 50
    
    score = 0
    new_lower = new_title.lower()
    new_fp = get_song_fingerprint(new_title)
    old_fp = context.get("fingerprint", "")
    
    # SAME SONG = BIG PENALTY
    if new_fp and old_fp:
        if new_fp == old_fp or new_fp in old_fp or old_fp in new_fp:
            return -1000  # Dead penalty
    
    # Artist match
    artist = context.get("artist", "")
    if artist and artist.lower() in new_lower:
        score += 100
    
    # Movie match
    movie = context.get("movie", "")
    if movie and movie.lower() in new_lower:
        score += 80
    
    # Core words match
    for w in context.get("core_words", []):
        if len(w) > 3 and w in new_lower:
            score += 15
    
    return score


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FIND SONG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def find_next_song(chat_id, context, last_vidid):
    if not context:
        return None, None
    
    queries = build_queries(context)
    candidates = []
    
    for q in queries:
        try:
            info, vid = await yt.track(q)
            if not vid or vid == last_vidid:
                continue
            
            title = info.get("title", "")
            duration = info.get("duration_min", "0:00")
            
            # Duration: 1.5 to 8 minutes
            try:
                if ":" in duration:
                    mins = int(duration.split(":")[0])
                else:
                    mins = int(float(duration))
                if mins < 1.5 or mins > 8:
                    continue
            except:
                continue
            
            # No compilations
            t_lower = title.lower()
            if any(x in t_lower for x in ["top", "hits", "jukebox", "playlist", "best of", "non stop", "megamix"]):
                continue
            
            # Score
            score = calculate_score(title, context)
            
            # Repeat check
            if await is_repeat(chat_id, vid, title):
                continue
            
            if score > 30:
                candidates.append((score, vid, info))
                
        except:
            continue
        await asyncio.sleep(0.1)
    
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], candidates[0][2]
    
    return None, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THUMBNAIL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_thumbnail(vid):
    async with aiohttp.ClientSession() as s:
        for url in [f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"]:
            try:
                async with s.get(url) as r:
                    if r.status == 200:
                        return url
            except:
                continue
    return f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN AUTOPLAY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(chat_id, original_chat_id, last_title="", last_vidid=""):
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream
    from strings import get_string
    
    if AUTO_PLAYING.get(chat_id):
        return False
    
    AUTO_PLAYING[chat_id] = True
    
    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False
        
        if last_vidid and last_title:
            await add_recent(chat_id, last_vidid, last_title)
            await save_context(chat_id, last_title, last_vidid, "00:00")
        
        await app.send_message(original_chat_id, "🔄 ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ...")
        
        context = await get_context(chat_id)
        
        if not context and last_title:
            context = {
                "title": last_title,
                "vidid": last_vidid,
                "artist": extract_artist(last_title),
                "movie": extract_movie(last_title),
                "fingerprint": get_song_fingerprint(last_title),
                "core_words": extract_core_words(last_title)
            }
        
        vid, info = await find_next_song(chat_id, context, last_vidid)
        
        if not vid and context:
            artist = context.get("artist", "")
            if artist:
                info, vid = await yt.track(f"{artist} songs")
        if not vid:
            info, vid = await yt.track("popular songs")
        if not vid:
            info, vid = await yt.track("trending music")
        
        if not vid:
            return False
        
        new_title = info.get("title", "")
        await add_recent(chat_id, vid, new_title)
        await save_context(chat_id, new_title, vid, info.get("duration_min", "00:00"))
        
        await stream(
            get_string(await get_lang(chat_id)),
            None,
            app.id,
            {
                "link": f"https://youtube.com/watch?v={vid}",
                "vidid": vid,
                "title": info.get("title", "🎵 ꜱᴏɴɢ"),
                "duration_min": info.get("duration_min", "00:00"),
                "thumb": await get_thumbnail(vid),
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )
        return True
        
    except Exception:
        return False
    finally:
        AUTO_PLAYING.pop(chat_id, None)
