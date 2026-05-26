import os
import aiofiles
import aiohttp
from PIL import Image
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from VISHALMUSIC.core.dir import CACHE_DIR


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_original.png")
    if os.path.exists(cache_path):
        return cache_path

    # YouTube ki original high quality thumbnail URL
    # Maxresdefault sabse best quality hoti hai
    thumbnail_urls = [
        f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{videoid}/sddefault.jpg",
        f"https://img.youtube.com/vi/{videoid}/mqdefault.jpg",
    ]
    
    thumb_path = None
    downloaded = False
    
    # Try each quality until one works
    for url in thumbnail_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.jpg")
                        async with aiofiles.open(thumb_path, "wb") as f:
                            await f.write(await resp.read())
                        downloaded = True
                        break
        except Exception:
            continue
    
    if not downloaded:
        return YOUTUBE_IMG_URL

    # Original thumbnail - no modification
    img = Image.open(thumb_path)

    # Cleanup
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    img.save(cache_path)
    return cache_path
