import os
import re
import random
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from io import BytesIO
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from VISHALMUSIC.core.dir import CACHE_DIR


PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 170
INNER_OFFSET = 36

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = 377
META_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580

# Random color accents for variety
ACCENTS = [
    (255, 102, 204),   # pink
    (102, 204, 255),   # blue
    (255, 153, 102),   # orange
    (153, 102, 255),   # purple
    (102, 255, 178),   # mint
    (255, 255, 102),   # yellow
    (255, 51, 153),    # hot pink
    (51, 255, 255),    # cyan
    (255, 102, 0),     # bright orange
    (102, 0, 255),     # deep violet
    (0, 255, 102),     # neon green
    (255, 0, 102),     # fuchsia
    (0, 204, 255),     # sky blue
    (204, 0, 255),     # magenta
    (255, 204, 102),   # goldish
]

# DeepAI API Configuration
DEEPAI_API_KEY = "73d89fb0-2cf8-4f29-8436-7a6803ad525c"
BACKGROUND_CACHE_DIR = os.path.join(CACHE_DIR, "anime_backgrounds")
MAX_CACHED_BG = 15

# Emergency flag file - when True, use YouTube thumbnail directly
EMERGENCY_FLAG_FILE = os.path.join(CACHE_DIR, ".emergency_mode")
API_FAIL_COUNT_FILE = os.path.join(CACHE_DIR, ".api_fail_count")
MAX_CONSECUTIVE_FAILS = 3


def set_emergency_mode(enable: bool):
    """Enable or disable emergency mode"""
    if enable:
        with open(EMERGENCY_FLAG_FILE, 'w') as f:
            f.write('1')
    else:
        if os.path.exists(EMERGENCY_FLAG_FILE):
            os.remove(EMERGENCY_FLAG_FILE)


def is_emergency_mode() -> bool:
    """Check if emergency mode is active"""
    return os.path.exists(EMERGENCY_FLAG_FILE)


def record_api_failure():
    """Record API failure for emergency detection"""
    fail_count = 0
    if os.path.exists(API_FAIL_COUNT_FILE):
        with open(API_FAIL_COUNT_FILE, 'r') as f:
            try:
                fail_count = int(f.read().strip())
            except:
                fail_count = 0
    
    fail_count += 1
    with open(API_FAIL_COUNT_FILE, 'w') as f:
        f.write(str(fail_count))
    
    if fail_count >= MAX_CONSECUTIVE_FAILS:
        set_emergency_mode(True)
        print("Emergency mode ACTIVATED - Using YouTube thumbnails directly")


def reset_api_failures():
    """Reset API failure counter on success"""
    if os.path.exists(API_FAIL_COUNT_FILE):
        os.remove(API_FAIL_COUNT_FILE)


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


async def get_random_anime_background() -> Image.Image:
    """
    Generate random 4K anime girl wallpaper using DeepAI
    Returns None if fails (will trigger emergency mode)
    """
    # Create cache directory if not exists
    os.makedirs(BACKGROUND_CACHE_DIR, exist_ok=True)
    
    # Emergency mode check
    if is_emergency_mode():
        print("Emergency mode ACTIVE - Skipping DeepAI background generation")
        return None
    
    # Try to use cached background first (70% of time to save API calls)
    cached_files = [f for f in os.listdir(BACKGROUND_CACHE_DIR) if f.endswith('.png')]
    if cached_files and random.random() < 0.7:
        chosen = random.choice(cached_files)
        try:
            bg_path = os.path.join(BACKGROUND_CACHE_DIR, chosen)
            img = Image.open(bg_path).convert("RGBA")
            img = img.resize((1280, 720))
            print(f"Using cached anime background: {chosen}")
            return img
        except Exception as e:
            print(f"Error loading cached background: {e}")
    
    # Generate new background from DeepAI
    anime_prompts = [
        "anime girl 4k wallpaper, ultra detailed, beautiful lighting, masterpiece, vibrant colors, high quality illustration",
        "cute anime girl portrait, 4k, vibrant colors, high quality illustration, detailed eyes, smooth shading",
        "anime girl in nature, 4k wallpaper, detailed background, soft lighting, cherry blossoms, magical atmosphere",
        "magical anime girl, 4k, fantasy art, glowing effects, cinematic lighting, ethereal, detailed dress",
        "anime girl in cyberpunk city, 4k wallpaper, neon lights, detailed illustration, futuristic, rain",
        "anime girl in traditional japanese garden, 4k, cherry blossoms, detailed artwork, serene, sunset lighting",
        "anime girl with flowing hair, 4k wallpaper, stars in background, dreamy, pastel colors, glitter effects",
        "anime girl winter aesthetic, 4k, snow, soft colors, cozy atmosphere, detailed illustration",
        "anime girl beach sunset, 4k, tropical vibes, vibrant colors, relaxing atmosphere, detailed",
        "anime girl fantasy forest, 4k, glowing mushrooms, magical creatures, enchanted atmosphere"
    ]
    
    async with aiohttp.ClientSession() as session:
        url = "https://api.deepai.org/api/text2img"
        headers = {"api-key": DEEPAI_API_KEY}
        
        # Select random prompt for variety
        prompt = random.choice(anime_prompts)
        print(f"Generating new anime background with prompt: {prompt[:50]}...")
        
        data = {"text": prompt, "grid_size": "1"}
        
        try:
            async with session.post(url, headers=headers, data=data, timeout=30) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    image_url = result.get("output_url")
                    
                    if image_url:
                        # Download generated image
                        async with session.get(image_url) as img_resp:
                            img_data = await img_resp.read()
                            img = Image.open(BytesIO(img_data)).convert("RGBA")
                            img = img.resize((1280, 720), Image.Resampling.LANCZOS)
                            
                            # Cache this image
                            timestamp = int(random.random() * 1000000)
                            cache_name = f"anime_bg_{timestamp}.png"
                            cache_path = os.path.join(BACKGROUND_CACHE_DIR, cache_name)
                            img.save(cache_path, "PNG")
                            
                            # Manage cache size - keep only MAX_CACHED_BG recent files
                            all_cached = sorted([f for f in os.listdir(BACKGROUND_CACHE_DIR) if f.endswith('.png')])
                            while len(all_cached) > MAX_CACHED_BG:
                                oldest = all_cached.pop(0)
                                try:
                                    os.remove(os.path.join(BACKGROUND_CACHE_DIR, oldest))
                                    print(f"Removed old cache: {oldest}")
                                except:
                                    pass
                            
                            # Reset failure counter on success
                            reset_api_failures()
                            
                            print("Successfully generated new anime background")
                            return img
                else:
                    print(f"DeepAI API returned status {resp.status}")
                    record_api_failure()
                    
        except asyncio.TimeoutError:
            print("DeepAI API timeout")
            record_api_failure()
        except Exception as e:
            print(f"DeepAI API error: {e}")
            record_api_failure()
    
    return None


def create_gradient_background(accent: tuple) -> Image.Image:
    """Fallback gradient background (used in emergency mode)"""
    base = Image.new('RGBA', (1280, 720), (0, 0, 0, 255))
    gradient = Image.new("RGBA", base.size, 0)
    
    for y in range(720):
        r, g, b = accent
        # Create smooth gradient
        factor = y / 720
        color = (
            int(r * factor),
            int(g * (1 - factor)),
            int(b * (0.5 + factor/2)),
            255
        )
        ImageDraw.Draw(gradient).line([(0, y), (1280, y)], fill=color)
    
    # Apply blur for smooth look
    gradient = gradient.filter(ImageFilter.GaussianBlur(radius=2))
    return gradient


def create_youtube_thumbnail_background(thumb_path: str) -> Image.Image:
    """Use YouTube thumbnail as background (emergency fallback)"""
    try:
        img = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
        # Apply blur and darken
        img = img.filter(ImageFilter.GaussianBlur(radius=15))
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 120))
        img = Image.alpha_composite(img, overlay)
        return img
    except Exception as e:
        print(f"Error creating YouTube thumbnail background: {e}")
        # Ultimate fallback - solid dark color
        return Image.new('RGBA', (1280, 720), (20, 20, 30, 255))


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v5_premium.png")
    if os.path.exists(cache_path):
        return cache_path

    # Fetch YouTube video data
    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        data = results_data.get("result", [])[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumbnail, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown Views"

    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"

    # Download YouTube thumbnail
    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    return YOUTUBE_IMG_URL
    except Exception:
        return YOUTUBE_IMG_URL

    # Get random accent color
    accent = random.choice(ACCENTS)
    
    # Create background based on mode
    if is_emergency_mode():
        print(f"Emergency mode: Using YouTube thumbnail as background for {videoid}")
        bg = create_youtube_thumbnail_background(thumb_path)
    else:
        # Try to get anime background from DeepAI
        anime_bg = await get_random_anime_background()
        
        if anime_bg:
            # Apply effects for better text readability
            bg = anime_bg.filter(ImageFilter.GaussianBlur(radius=3))
            # Add dark overlay for text contrast
            overlay = Image.new("RGBA", bg.size, (0, 0, 0, 100))
            bg = Image.alpha_composite(bg, overlay)
        else:
            # Fallback to gradient if API fails but emergency not triggered yet
            print("Using gradient fallback background")
            bg = create_gradient_background(accent)

    # Frosted glass panel
    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel_area, overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    # Text & fonts
    draw = ImageDraw.Draw(bg)
    try:
        title_font = ImageFont.truetype("VISHALMUSIC/assets/thumb/font2.ttf", 36)
        regular_font = ImageFont.truetype("VISHALMUSIC/assets/thumb/font.ttf", 20)
        heart_font = ImageFont.truetype("VISHALMUSIC/assets/thumb/font2.ttf", 26)
    except OSError:
        title_font = regular_font = heart_font = ImageFont.load_default()

    # Thumbnail image (the actual video thumbnail)
    thumb_img = Image.open(thumb_path).resize((THUMB_W, THUMB_H)).convert("RGBA")
    tmask = Image.new("L", thumb_img.size, 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 25, fill=255)
    bg.paste(thumb_img, (THUMB_X, THUMB_Y), tmask)

    # Neon title text with shadow
    title_text = trim_to_width(title, title_font, MAX_TITLE_WIDTH)
    shadow_pos = (TITLE_X + 2, TITLE_Y + 2)
    draw.text(shadow_pos, title_text, font=title_font, fill=(0, 0, 0, 160))
    draw.text((TITLE_X, TITLE_Y), title_text, font=title_font, fill=accent)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill=(40, 40, 40), font=regular_font)

    # Stylish progress bar
    bar_y = BAR_Y
    draw.line([(BAR_X, bar_y), (BAR_X + BAR_TOTAL_LEN, bar_y)], fill="black", width=6)
    draw.line([(BAR_X, bar_y), (BAR_X + BAR_RED_LEN, bar_y)], fill=accent, width=6)

    # Heart symbol above progress
    heart_symbol = "♡゙"
    heart_x = BAR_X + BAR_RED_LEN - 10
    heart_y = bar_y - 30
    draw.text((heart_x, heart_y), heart_symbol, fill=accent, font=heart_font)

    draw.text((BAR_X, bar_y + 15), "00:00", fill="black", font=regular_font)
    end_text = "Live" if is_live else duration_text
    draw.text((BAR_X + BAR_TOTAL_LEN - 90, bar_y + 15), end_text, fill=accent, font=regular_font)

    # Icons
    icons_path = "VISHALMUSIC/assets/thumb/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
        ic_gray = ic.convert("L")
        ic_colored = ImageOps.colorize(ic_gray, black="black", white=f"rgb{accent}").convert("RGBA")
        ic_colored.putalpha(ic.split()[-1])
        bg.paste(ic_colored, (ICONS_X, ICONS_Y), ic_colored)

    # Add emergency mode watermark (optional - for debugging)
    if is_emergency_mode():
        watermark_font = ImageFont.truetype("VISHALMUSIC/assets/thumb/font.ttf", 14) if not isinstance(regular_font, ImageFont.ImageFont) else regular_font
        draw.text((10, 10), "⚠️ EMERGENCY MODE", fill=(255, 100, 100), font=watermark_font)

    # Cleanup
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    bg.save(cache_path)
    return cache_path


# Utility function to manually control emergency mode
def emergency_override(enable: bool = None):
    """Manually control emergency mode. If enable is None, toggles mode."""
    current = is_emergency_mode()
    if enable is None:
        enable = not current
    
    set_emergency_mode(enable)
    status = "ENABLED" if enable else "DISABLED"
    print(f"Emergency mode {status}")
    
    if not enable:
        reset_api_failures()
    
    return enable
