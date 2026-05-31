import asyncio
import random
import re
import time
import math

import aiohttp

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🔥 SMART PROTECTION SYSTEM (Enhanced)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
RECENT_TITLES = {}
AUTO_PLAYING = {}
CHAT_CONTEXT = {}  # Store last 5 songs context for better matching

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🇮🇳 COMPLETE INDIAN DATABASES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANG_DB = {
    "hindi": ["hindi", "bollywood", "arijit", "jubin", "atif", "hindi song", "bollywood song", "hindhi", "indian"],
    "punjabi": ["punjabi", "sidhu", "diljit", "karan", "ammy", "jatt", "punjabi song", "pind", "punjab"],
    "english": ["english", "ed sheeran", "taylor swift", "justin bieber", "english song", "international"],
    "bhojpuri": ["bhojpuri", "pawan singh", "khesari", "bhojpuri song", "bhojpuria"],
    "haryanvi": ["haryanvi", "khasa", "masoom sharma", "haryanvi song", "hr"],
    "gujarati": ["gujarati", "gujju", "garba", "gujarati song", "gujrat"],
    "tamil": ["tamil", "tamil song", "kollywood", "anirudh", "tamil cinema", "chennai"],
    "telugu": ["telugu", "telugu song", "tollywood", "devi sri", "telugu cinema", "hyderabad"],
    "bengali": ["bengali", "bangla", "bengali song", "kolkata"],
    "marathi": ["marathi", "marathi song", "maharashtra", "pune"],
    "urdu": ["urdu", "urdu song", "pakistani", "nusrat", "ghazal"],
    "rap": ["rap", "hip hop", "divine", "emiway", "raftaar", "badshah", "king", "mc stan"],
}

MOOD_DB = {
    "sad": ["sad", "broken", "heart", "bewafa", "alone", "cry", "dard", "tanha", "rula", "sad song", "depress", "hurt", "tut gya"],
    "love": ["love", "romantic", "ishq", "pyaar", "mohabbat", "love song", "romantic song", "pyar", "ishq wala", "valentine", "couple"],
    "party": ["party", "dj", "dance", "club", "bhangra", "party song", "dj song", "dance song", "masala", "vibe", "masti"],
    "wedding": ["wedding", "shaadi", "marriage", "dulhan", "mehendi", "sangeet", "band baaja"],
    "devotional": ["devotional", "bhajan", "aarti", "mantra", "shiva", "krishna", "ram", "ganesha", "hanuman", "chalisa"],
    "oldschool": ["old", "classic", "90s", "80s", "kishore", "lata", "rafi", "old song", "retro", "purana", "evergreen"],
    "sufi": ["sufi", "qawwali", "nusrat", "kalam", "sufiana", "bulleh shah"],
    "workout": ["workout", "gym", "motivation", "pump", "workout song", "fitness", "running"],
    "travel": ["travel", "road trip", "journey", "jaane na", "safar", "highway"],
    "rain": ["rain", "barish", "baarish", "rainy", "wet"],
}

ARTIST_DB = {
    "arijit singh": ["arijit", "arijit singh", "arijit song", "arijit new", "arijit hit"],
    "atif aslam": ["atif", "atif aslam", "atif song", "tajdar e haram"],
    "sidhu moosewala": ["sidhu", "sidhu moosewala", "sidhu song", "moosewala", "last ride"],
    "diljit dosanjh": ["diljit", "diljit dosanjh", "diljit song", "proper patola"],
    "karan aujla": ["karan", "karan aujla", "karan song", "aujla", "gaddi red challenger"],
    "jubin nautiyal": ["jubin", "jubin nautiyal", "jubin song", "tum hi aana"],
    "badshah": ["badshah", "badshah song", "gully boy", "judgement"],
    "yo yo honey singh": ["honey singh", "yo yo", "brown rang", "yo yo honey singh", "blue eyes"],
    "neha kakkar": ["neha kakkar", "neha song", "neha new", "kalla sohna"],
    "shreya ghoshal": ["shreya", "shreya ghoshal", "shreya song", "teri meri"],
    "sonu nigam": ["sonu", "sonu nigam", "sonu song", "kal ho na ho"],
    "alka yagnik": ["alka", "alka yagnik", "alka song", "tip tip barsa pani"],
    "udit narayan": ["udit", "udit narayan", "udit song", "papa kehte hain"],
    "kumar sanu": ["kumar sanu", "kumar song", "do dil mil rahe hain"],
    "lata mangeshkar": ["lata", "lata mangeshkar", "lata song", "ae mere watan ke logo"],
    "kishore kumar": ["kishore", "kishore kumar", "kishore song", "pal pal dil ke paas"],
    "mohammad rafi": ["rafi", "mohammad rafi", "rafi song", "chaudhvin ka chand"],
    "ap dhillon": ["ap dhillon", "ap", "dhillon", "ap song", "brown munde", "gurinder gill"],
    "gurinder gill": ["gurinder gill", "gill", "gurinder song", "dont look"],
    "king": ["king", "king song", "tu aake dekh le", "mishri"],
    "mc stan": ["mc stan", "stan", "stan song", "khuja mat", "basti ka hasti"],
    "divine": ["divine", "divine song", "gully gang", "kohinoor", "baazigar"],
    "raftaar": ["raftaar", "raftaar song", "naachne ka shauq", "black sheep"],
}

MOVIE_DB = {
    "animal": ["animal", "animal song", "animal movie", "ranbir", "sandhu"],
    "kabir singh": ["kabir singh", "kabir movie", "shahid", "tujhe kitna chahne lage"],
    "aashiqui 2": ["aashiqui", "aashiqui 2", "tum hi ho", "aditya roy kapoor"],
    "shershaah": ["shershaah", "shershaah song", "sidharth malhotra", "raanjha"],
    "pushpa": ["pushpa", "pushpa song", "srivali", "allu arjun", "samantha"],
    "kgf": ["kgf", "kgf song", "rocky bhai", "yash", "salaam rocky"],
    "pathaan": ["pathaan", "pathaan song", "shah rukh", "deepika", "besharam rang"],
    "jawan": ["jawan", "jawan song", "nayak nahi khalnayak", "vijay sethupathi"],
    "dunki": ["dunki", "dunki song", "tauba tauba", "shah rukh"],
    "gadar 2": ["gadar", "gadar 2", "utthe sab ke kadam", "sunny deol"],
    "rocky aur rani": ["rocky", "rani", "rocky aur rani", "kjo", "ranveer", "alia"],
    "tu jhoothi main makkaar": ["tu jhoothi", "tjmm", "ranbir", "shraddha", "pyaar hota hai"],
    "bhool bhulaiyaa 2": ["bhool bhulaiyaa", "bb2", "kartik aaryan", "kiara"],
    "brahmastra": ["brahmastra", "astra", "ranbir", "alia", "kesariya"],
    "tanhaji": ["tanhaji", "ajay devgn", "tanhaji song", "shivaji maharaj"],
    "chhichhore": ["chhichhore", "sushant", "chhichhore song", "faraatta"],
    "yeh jawani hai deewani": ["yjhd", "yeh jawani", "deewani", "ranbir", "deepika", "badtameez dil"],
    "zindagi na milegi dobara": ["znmd", "zindagi na milegi", "hritik", "kabira"],
    "3 idiots": ["3 idiots", "three idiots", "amir khan", "all is well"],
    "dangal": ["dangal", "amir khan", "dangal song", "haryana"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🤖 AI-LIKE INTELLIGENT FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_lang(title):
    if not title:
        return "hindi"
    title = title.lower()
    scores = {}
    for lang, keys in LANG_DB.items():
        score = sum(2 if key in title else 0 for key in keys)
        if score > 0:
            scores[lang] = score
    if scores:
        return max(scores, key=scores.get)
    return "hindi"

def detect_mood(title):
    if not title:
        return "normal"
    title = title.lower()
    scores = {}
    for mood, keys in MOOD_DB.items():
        score = sum(3 if key in title else 0 for key in keys)
        if score > 0:
            scores[mood] = score
    if scores:
        return max(scores, key=scores.get)
    return "normal"

def extract_artist(title):
    if not title:
        return ""
    title_lower = title.lower()
    for artist, keys in ARTIST_DB.items():
        for key in keys:
            if key in title_lower:
                return artist
    parts = re.split(r"[-|(]|feat|ft", title)
    if len(parts) > 1:
        candidate = parts[0].strip()
        if len(candidate) < 35:
            return candidate
    return ""

def detect_movie(title):
    if not title:
        return ""
    title = title.lower()
    for movie, keys in MOVIE_DB.items():
        for key in keys:
            if key in title:
                return movie
    return ""

def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower().strip()
    for sep in [" - ", " | ", " — ", " ft ", " feat ", " (", " ["]:
        if sep in t:
            t = t.split(sep)[0].strip()
            break
    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", "", t)
    noise = ["official", "video", "music", "audio", "lyrics", "lyrical", "lyric", "full", "hd", "hq", "4k", "song", "new", "latest", "visualizer", "teaser", "promo", "reaction", "review"]
    for w in noise:
        t = re.sub(rf"\b{w}\b", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[^\w\s]", "", t)
    return t

def _same_song(stored: str, candidate: str) -> bool:
    if not stored or not candidate:
        return False
    stored = stored.lower().strip()
    candidate = candidate.lower().strip()
    if stored == candidate:
        return True
    if len(stored) > 5 and len(candidate) > 5:
        if stored in candidate or candidate in stored:
            return True
    stored_words = set(stored.split())
    candidate_words = set(candidate.split())
    if stored_words and candidate_words:
        common = stored_words.intersection(candidate_words)
        ratio = len(common) / max(len(stored_words), len(candidate_words))
        if ratio >= 0.65:
            return True
    return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🔁 REPEAT CHECK (6 hours memory)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title: str = "") -> bool:
    current = time.time()
    MEMORY_TIME = 21600  # 6 hours
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if current - t < MEMORY_TIME]
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [(n, t) for n, t in RECENT_TITLES[chat_id] if current - t < MEMORY_TIME]
            for stored_norm, _ in RECENT_TITLES[chat_id]:
                if _same_song(stored_norm, norm):
                    return True
    return False

async def add_recent(chat_id, vidid, title: str = "") -> None:
    if not vidid:
        return
    current = time.time()
    MEMORY_TIME = 21600
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, current))
    if len(RECENT[chat_id]) > 150:
        RECENT[chat_id] = RECENT[chat_id][-150:]
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm, current))
            if len(RECENT_TITLES[chat_id]) > 150:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-150:]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🧠 AI-POWERED QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood):
    queries = []
    clean_title = re.sub(r"official|video|lyrics|lyrical|hd|4k|music|song|audio|full|hq", "", title, flags=re.IGNORECASE).strip()
    
    # WEIGHTED QUERIES (Higher weight = better match)
    query_weights = []
    
    if artist and movie:
        query_weights.append((100, f"{artist} {movie} song"))
        query_weights.append((95, f"{movie} {artist}"))
        query_weights.append((90, f"{artist} {movie} hit"))
    
    if artist:
        query_weights.append((85, f"{artist} songs"))
        query_weights.append((80, f"{artist} hits"))
        query_weights.append((75, f"{artist} best songs"))
        query_weights.append((70, f"{artist} new song 2025"))
        query_weights.append((65, f"{artist} all songs"))
    
    if movie:
        query_weights.append((80, f"{movie} songs"))
        query_weights.append((75, f"{movie} all songs"))
        query_weights.append((70, f"{movie} jukebox"))
        query_weights.append((65, f"{movie} movie songs"))
    
    if lang and mood:
        mood_map = {"sad": "sad", "love": "romantic", "party": "party", "workout": "workout"}
        mood_word = mood_map.get(mood, mood)
        query_weights.append((60, f"{mood_word} {lang} songs"))
    
    if lang:
        query_weights.append((50, f"{lang} songs 2025"))
        query_weights.append((45, f"best {lang} songs"))
        query_weights.append((40, f"{lang} hits"))
    
    if clean_title and len(clean_title) > 5:
        query_weights.insert(0, (100, clean_title))
    
    # FALLBACK
    query_weights.append((20, "bollywood songs 2025"))
    query_weights.append((15, "hindi trending songs"))
    query_weights.append((10, "viral bollywood songs"))
    
    bad_words = ["slowed", "reverb", "lofi", "8d", "live concert", "full movie", "episode", "non-stop", "megamix"]
    
    final = []
    for weight, q in query_weights:
        q_lower = q.lower()
        if not any(bad in q_lower for bad in bad_words):
            if q not in final and len(q) > 3:
                final.append(q)
    
    return final[:20]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🎯 ADVANCED BEST SONG FINDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_best_song(chat_id, queries, last_title, last_vidid, artist, movie, mood, lang):
    candidates = []
    original_words = set(last_title.lower().split())
    
    for q in queries:
        try:
            details, vidid = await yt.track(q)
            if not vidid or vidid == last_vidid:
                continue
            
            title = details.get("title", "").lower()
            duration = details.get("duration_min", "0:00") or "0:00"
            
            # DURATION CHECK
            try:
                if ":" in duration:
                    parts = duration.split(":")
                    mins = int(parts[0])
                    secs = int(parts[1]) if len(parts) > 1 else 0
                else:
                    mins = int(float(duration))
                    secs = 0
                
                if mins < 0.5 or mins > 12:  # 30 sec to 12 min only
                    continue
            except:
                continue
            
            # FILTER BAD CONTENT
            bad = ["live", "concert", "full movie", "episode", "slowed", "reverb", "lofi", "8d", "sped up", "cover", "karaoke", "instrumental", "non-stop", "megamix", "dj mix"]
            if any(x in title for x in bad):
                continue
            
            # SMART SCORING SYSTEM
            score = 0
            
            # ARTIST MATCH (Highest weight)
            if artist:
                if artist.lower() in title:
                    score += 120
                    if title.startswith(artist.lower()):
                        score += 60
                # Check partial match
                artist_parts = artist.lower().split()
                if any(part in title and len(part) > 3 for part in artist_parts):
                    score += 40
            
            # MOVIE MATCH
            if movie and movie.lower() in title:
                score += 90
            
            # LANGUAGE MATCH
            lang_score = 0
            for key in LANG_DB.get(lang, []):
                if key in title:
                    lang_score += 15
            score += min(lang_score, 50)
            
            # MOOD MATCH
            mood_score = 0
            for key in MOOD_DB.get(mood, []):
                if key in title:
                    mood_score += 12
            score += min(mood_score, 40)
            
            # TITLE WORD MATCH
            title_words = set(title.split())
            common_words = original_words.intersection(title_words)
            score += len(common_words) * 8
            
            # DURATION BONUS (2-5 min is ideal)
            if 2 <= mins <= 5:
                score += 20
            elif 5 < mins <= 8:
                score += 5
            elif mins > 8:
                score -= 15
            
            # LANGUAGE PENALTY
            if lang == "hindi":
                if "punjabi" in title:
                    score -= 60
                if "english" in title and "remix" not in title:
                    score -= 50
                if "tamil" in title or "telugu" in title:
                    score -= 70
            elif lang == "punjabi":
                if "hindi" in title and "remix" not in title:
                    score -= 50
            
            # REPEAT CHECK
            if await is_repeat(chat_id, vidid, title):
                score -= 200
            
            if score > 30:
                candidates.append((score, vidid, details))
                
        except Exception:
            continue
        
        await asyncio.sleep(0.1)
    
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], candidates[0][2]
    
    return None, None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🖼 THUMBNAIL & EMOJI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
            except:
                continue
    return urls[-1]

def get_indian_emoji():
    emojis = ["🇮🇳", "🎧", "❤️", "🎶", "✨", "🎤", "💖", "🎵", "🔥", "💫", "🎸", "💕", "🪩", "🌙", "💘", "🥰", "🎼", "⚡", "💞", "🦋", "💜", "🌸", "🕺", "💃", "💝", "🌈", "❣️", "🪘", "💗"]
    return random.choice(emojis)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🚀 MAIN AUTOPLAY (ULTRA POWERFUL)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(
    chat_id: int,
    original_chat_id: int,
    last_title: str = "",
    last_vidid: str = "",
) -> bool:
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

        indian_emoji = get_indian_emoji()

        try:
            msg = await app.send_message(
                original_chat_id,
                f"{indian_emoji} **ᴀᴜᴛᴏᴘʟᴀʏ** → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ... 🎯",
            )
        except:
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

        # POWERFUL FALLBACK CHAIN
        fallback_queries = []
        if movie:
            fallback_queries.extend([f"{movie} songs", f"{movie} hits", f"{movie} playlist"])
        if artist:
            fallback_queries.extend([f"{artist} songs", f"{artist} hits", f"{artist} popular"])
        if lang:
            fallback_queries.extend([f"{lang} songs 2025", f"top {lang} songs", f"{lang} hits"])
        
        fallback_queries.extend(["bollywood hits 2025", "hindi songs 2025", "trending hindi songs", "viral bollywood"])

        for fq in fallback_queries:
            if vidid:
                break
            try:
                details, vidid = await yt.track(fq)
                if vidid == last_vidid:
                    vidid = None
            except:
                continue

        if not vidid:
            try:
                await msg.edit_text("❌ **ɴᴏ ꜱᴏɴɢ ꜰᴏᴜɴᴅ**\nᴀᴜᴛᴏᴘʟᴀʏ ꜱᴛᴏᴘᴘᴇᴅ")
            except:
                pass
            return False

        new_title = details.get("title", "") if details else ""
        await add_recent(chat_id, vidid, new_title)

        link = f"https://youtube.com/watch?v={vidid}"

        try:
            thumb = details.get("thumb", "")
            if not thumb or not thumb.startswith("http"):
                thumb = await get_thumbnail_direct(vidid)
        except:
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
                "title": details.get("title", "🇮🇳 ɪɴᴅɪᴀɴ ꜱᴏɴɢ"),
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
        except:
            pass

        return True

    except Exception as e:
        return False

    finally:
        AUTO_PLAYING.pop(chat_id, None)
