import os
import re
import random
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
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


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


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

    # Download thumbnail
    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
    except Exception:
        return YOUTUBE_IMG_URL

    # Base gradient background
    accent = random.choice(ACCENTS)
    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    gradient = Image.new("RGBA", base.size, 0)
    for y in range(720):
        r, g, b = accent
        color = (int(r * (y / 720)), int(g * (1 - y / 720)), int(b * (0.5 + y / 1440)), 255)
        ImageDraw.Draw(gradient).line([(0, y), (1280, y)], fill=color)
    bg = Image.alpha_composite(base, gradient)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.BoxBlur(10))).enhance(0.7)

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
    except OSError:
        title_font = regular_font = ImageFont.load_default()

    # Thumb image
    thumb = base.resize((THUMB_W, THUMB_H))
    tmask = Image.new("L", thumb.size, 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 25, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    # Neon title text with shadow
    title_text = trim_to_width(title, title_font, MAX_TITLE_WIDTH)
    shadow_pos = (TITLE_X + 2, TITLE_Y + 2)
    draw.text(shadow_pos, title_text, font=title_font, fill=(0, 0, 0, 160))
    draw.text((TITLE_X, TITLE_Y), title_text, font=title_font, fill=accent)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill=(40, 40, 40), font=regular_font)

    # Stylish progress bar ♡゙
    bar_y = BAR_Y
    draw.line([(BAR_X, bar_y), (BAR_X + BAR_TOTAL_LEN, bar_y)], fill="black", width=6)
    draw.line([(BAR_X, bar_y), (BAR_X + BAR_RED_LEN, bar_y)], fill=accent, width=6)

    # Heart symbol above progress
    heart_symbol = "♡゙"
    heart_font = ImageFont.truetype("VISHALMUSIC/assets/thumb/font2.ttf", 26)
    heart_x = BAR_X + BAR_RED_LEN - 10
    heart_y = bar_y - 30
    draw.text((heart_x, heart_y), heart_symbol, fill=accent, font=heart_font)

    draw.text((BAR_X, bar_y + 15), "00:00", fill="black", font=regular_font)
    end_text = "Live" if is_live else duration_text
    draw.text((BAR_X + BAR_TOTAL_LEN - 90, bar_y + 15), end_text, fill=accent, font=regular_font)

    # Icons (Fixed transparency issue)
    icons_path = "VISHALMUSIC/assets/thumb/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
        ic_gray = ic.convert("L")
        ic_colored = ImageOps.colorize(ic_gray, black="black", white=f"rgb{accent}").convert("RGBA")
        ic_colored.putalpha(ic.split()[-1])  # restore alpha
        bg.paste(ic_colored, (ICONS_X, ICONS_Y), ic_colored)

    # Cleanup
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    bg.save(cache_path)
    return cache_path
