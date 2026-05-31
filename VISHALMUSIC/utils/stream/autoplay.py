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

RECENT = {}
RECENT_TITLES = {}
AUTO_PLAYING = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PURE DYNAMIC EXTRACTORS (No keywords)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_core_words(title):
    """Extract unique meaningful words from title - no hardcode"""
    if not title:
        return []
    
    t = title.lower()
    
    # Remove common noise patterns
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\{[^}]*\}", "", t)
    
    # Split by separators
    for sep in [" - ", " | ", " — ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0]
            break
    
    # Extract words
    words = re.findall(r"[a-z]+(?:[a-z]+)*", t)
    
    # Filter short words and common noise
    noise = ["the", "and", "for", "with", "official", "video", "lyrics", "hd", "4k", "song", "new", "latest", "full", "audio", "lyrical"]
    
    result = []
    for w in words:
        if len(w) > 3 and w not in noise:
            result.append(w)
    
    return result

def get_primary_identifier(title, core_words):
    """Get main identifier (artist/movie guess) from title structure"""
    if not title or not core_words:
        return ""
    
    # Get text before first separator
    for sep in [" - ", " | ", " — "]:
        if sep in title:
            primary = title.split(sep)[0].strip()
            if len(primary) > 2 and len(primary) < 40:
                return primary
    
    # Get first 2-3 words as identifier
    if len(core_words) >= 2:
        return " ".join(core_words[:2])
    elif core_words:
        return core_words[0]
    
    return ""

def get_secondary_identifier(title, core_words):
    """Get secondary identifier (movie/album guess)"""
    if not title or not core_words:
        return ""
    
    # Look for patterns like "from X" or "movie X"
    patterns = [
        r'from\s+([a-z0-9\s]+?)(?:\s+[a-z]+)?$',
        r'movie\s+([a-z0-9\s]+?)$',
        r'album\s+([a-z0-9\s]+?)$',
        r'\((?:from\s+)?([a-z0-9\s]+?)\)'
    ]
    
    t = title.lower()
    for pattern in patterns:
        match = re.search(pattern, t)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) > 2 and len(candidate) < 35:
                return candidate
    
    # Get last few words if they seem like a movie
    if len(core_words) > 3:
        candidate = " ".join(core_words[-2:])
        if len(candidate) > 3:
            return candidate
    
    return ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TITLE NORMALIZER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def normalize_title(title):
    if not title:
        return ""
    t = title.lower().strip()
    for sep in [" - ", " | ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0]
    t = re.sub(r"[\(\[{].*?[\)\]}]", "", t)
    t = re.sub(r"\b(official|video|lyrics|hd|4k|song|audio|full|new|latest)\b", "", t)
    return re.sub(r"\s+", " ", t).strip()

def same_song(a, b):
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    words_a = set(a.split())
    words_b = set(b.split())
    if words_a and words_b:
        return len(words_a & words_b) / max(len(words_a), len(words_b)) > 0.6
    return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REPEAT PROTECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title=""):
    now = time.time()
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if now - t < 14400]
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True
    if title:
        norm = normalize_title(title)
        if norm:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [(n, t) for n, t in RECENT_TITLES[chat_id] if now - t < 14400]
            for sn, _ in RECENT_TITLES[chat_id]:
                if same_song(sn, norm):
                    return True
    return False

async def add_recent(chat_id, vidid, title=""):
    if not vidid:
        return
    now = time.time()
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, now))
    if len(RECENT[chat_id]) > 100:
        RECENT[chat_id] = RECENT[chat_id][-100:]
    if title:
        norm = normalize_title(title)
        if norm:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm, now))
            if len(RECENT_TITLES[chat_id]) > 100:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-100:]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QUERY BUILDER (Pure dynamic)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_queries(title, primary_id, secondary_id, core_words):
    queries = []
    
    # Original clean title
    clean = normalize_title(title)
    if clean and len(clean) > 4:
        queries.append(clean)
    
    # Primary identifier (artist)
    if primary_id and len(primary_id) > 2:
        queries.append(f"{primary_id} songs")
        queries.append(f"{primary_id} hits")
        queries.append(f"{primary_id} new")
    
    # Secondary identifier (movie)
    if secondary_id and len(secondary_id) > 2:
        queries.append(f"{secondary_id} songs")
        queries.append(f"{secondary_id} all")
    
    # Combined
    if primary_id and secondary_id:
        queries.insert(0, f"{primary_id} {secondary_id}")
    
    # Core words combination
    if len(core_words) >= 2:
        queries.append(" ".join(core_words[:3]))
    
    # Generic fallbacks (least priority)
    queries.append("popular songs")
    queries.append("trending music")
    queries.append("hits")
    
    # Remove duplicates and filter
    seen = set()
    final = []
    for q in queries:
        if q not in seen and len(q) > 3 and len(q) < 60:
            seen.add(q)
            final.append(q)
    
    return final[:12]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIMILARITY SCORING (No hardcode)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_similarity(title1, title2):
    """Calculate how similar two titles are - pure math"""
    if not title1 or not title2:
        return 0
    
    t1 = title1.lower()
    t2 = title2.lower()
    
    # Extract words
    words1 = set(re.findall(r"[a-z]+(?:[a-z]+)*", t1))
    words2 = set(re.findall(r"[a-z]+(?:[a-z]+)*", t2))
    
    # Remove very short words
    words1 = {w for w in words1 if len(w) > 2}
    words2 = {w for w in words2 if len(w) > 2}
    
    if not words1 or not words2:
        return 0
    
    # Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0

def calculate_context_score(new_title, last_title, primary_id, secondary_id):
    """Score based on context match - pure dynamic"""
    score = 0
    
    # Direct title similarity
    similarity = calculate_similarity(new_title, last_title)
    score += similarity * 100
    
    # Primary identifier match
    if primary_id and primary_id.lower() in new_title.lower():
        score += 60
    
    # Secondary identifier match
    if secondary_id and secondary_id.lower() in new_title.lower():
        score += 40
    
    # Core word overlap
    last_words = set(re.findall(r"[a-z]+", last_title.lower()))
    new_words = set(re.findall(r"[a-z]+", new_title.lower()))
    
    meaningful_overlap = 0
    for w in last_words:
        if len(w) > 3 and w in new_words:
            meaningful_overlap += 15
    score += meaningful_overlap
    
    return score

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FIND SONG (Pure logic)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def find_song(chat_id, queries, last_title, last_vidid, primary_id, secondary_id):
    candidates = []
    
    for q in queries:
        try:
            info, vid = await yt.track(q)
            if not vid or vid == last_vidid:
                continue
            
            title = info.get("title", "").lower()
            duration = info.get("duration_min", "0:00")
            
            # Duration check: between 1.5 and 8 minutes
            try:
                if ":" in duration:
                    mins = int(duration.split(":")[0])
                else:
                    mins = int(float(duration))
                if mins < 1.5 or mins > 8:
                    continue
            except:
                continue
            
            # Block obvious compilations (pattern based)
            t_lower = title.lower()
            compilation_patterns = [
                r'top\s+\d+', r'\d+\s+hits', r'\d+\s+songs',
                r'non[- ]?stop', r'jukebox', r'playlist', r'megamix'
            ]
            is_compilation = any(re.search(p, t_lower) for p in compilation_patterns)
            if is_compilation:
                continue
            
            # Block if title has 2+ numbers (likely compilation)
            if len(re.findall(r'\d+', t_lower)) >= 2:
                continue
            
            # Calculate context score
            score = calculate_context_score(title, last_title, primary_id, secondary_id)
            
            # Repeat check
            if await is_repeat(chat_id, vid, title):
                continue
            
            if score > 25:
                candidates.append((score, vid, info))
                
        except Exception:
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
        
        if last_vidid:
            await add_recent(chat_id, last_vidid, last_title)
        
        await app.send_message(original_chat_id, "🔄 ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ...")
        
        if not last_title:
            queue = db.get(chat_id)
            last_title = queue[0].get("title", "song") if queue else "song"
        
        # Pure dynamic extraction
        core_words = extract_core_words(last_title)
        primary_id = get_primary_identifier(last_title, core_words)
        secondary_id = get_secondary_identifier(last_title, core_words)
        
        queries = build_queries(last_title, primary_id, secondary_id, core_words)
        vid, info = await find_song(chat_id, queries, last_title, last_vidid, primary_id, secondary_id)
        
        # Fallbacks
        if not vid and primary_id:
            info, vid = await yt.track(f"{primary_id} songs")
        if not vid and secondary_id:
            info, vid = await yt.track(f"{secondary_id} songs")
        if not vid:
            info, vid = await yt.track("popular songs")
        if not vid:
            info, vid = await yt.track("trending")
        
        if not vid:
            return False
        
        await add_recent(chat_id, vid, info.get("title", ""))
        
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
