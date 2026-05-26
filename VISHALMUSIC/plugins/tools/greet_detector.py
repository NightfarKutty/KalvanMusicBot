import os
import io
import re
import time
import asyncio
import datetime
import html
from zoneinfo import ZoneInfo
from typing import List

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from PIL import Image, ImageDraw, ImageFont

from VISHALMUSIC import app

# Configuration via env
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
FONT_PATH = os.environ.get("FONT_PATH", "")  # optional: path to a .ttf font for nicer text
ALLOW_OUT_OF_TIME_REPLY = bool(os.environ.get("ALLOW_OUT_OF_TIME_REPLY", "").strip())  # if true, still reply even if time doesn't match

# Word patterns to detect greetings (case-insensitive)
GOODNIGHT_RE = re.compile(r"\b(good\s*night|goodnight|gn|nighty|nite)\b", re.IGNORECASE)
GOODMORNING_RE = re.compile(r"\b(good\s*morning|goodmorning|gm|morning|subah)\b", re.IGNORECASE)

# Time windows (local time)
def is_good_morning(dt_local: datetime.datetime) -> bool:
    return 4 <= dt_local.hour < 12  # 04:00 - 11:59

def is_good_night(dt_local: datetime.datetime) -> bool:
    return dt_local.hour >= 20 or dt_local.hour < 4  # 20:00 - 03:59

# Utility: create a stylized thumbnail image with text lines and username
def generate_thumbnail(lines: List[str], username: str = "", width: int = 1280, height: int = 720) -> bytes:
    # Colors & simple gradient background
    bg_top = (20, 20, 60)
    bg_bottom = (80, 10, 50)

    img = Image.new("RGBA", (width, height), bg_top)
    draw = ImageDraw.Draw(img)

    # vertical gradient
    for y in range(height):
        ratio = y / (height - 1)
        r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # overlay translucent dark box
    box_margin = 60
    box = (box_margin, box_margin, width - box_margin, height - box_margin)
    overlay = Image.new("RGBA", (width, height))
    od = ImageDraw.Draw(overlay)
    od.rectangle(box, fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)  # Recreate draw after composite

    # fonts
    def load_font(size: int):
        try:
            if FONT_PATH and os.path.exists(FONT_PATH):
                return ImageFont.truetype(FONT_PATH, size)
            # try common system fonts
            for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                      "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                      "/System/Library/Fonts/Helvetica.ttc",  # macOS
                      "C:\\Windows\\Fonts\\Arial.ttf"]:      # Windows
                if os.path.exists(p):
                    return ImageFont.truetype(p, size)
        except Exception:
            pass
        return ImageFont.load_default()

    title_font = load_font(72)
    sub_font = load_font(40)
    small_font = load_font(28)

    # Function to get text dimensions (compatible with newer Pillow)
    def get_text_size(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Draw lines centered
    center_x = width // 2
    # compute starting y to center all lines
    total_text_height = 0
    line_heights = []
    fonts = [title_font if i == 0 else sub_font for i in range(len(lines))]
    for i, ln in enumerate(lines):
        w, h = get_text_size(ln, fonts[i])
        line_heights.append((w, h))
        total_text_height += h + 18
    start_y = (height - total_text_height) // 2

    # Draw each line with shadow
    y = start_y
    for i, ln in enumerate(lines):
        f = fonts[i]
        w, h = line_heights[i]
        x = center_x - w // 2
        # shadow
        draw.text((x + 3, y + 3), ln, font=f, fill=(0, 0, 0, 200))
        # main text (gold-ish)
        draw.text((x, y), ln, font=f, fill=(255, 240, 160, 255))
        y += h + 18

    # draw username bottom-right
    if username:
        user_text = f"— {username}"
        w, h = get_text_size(user_text, font=small_font)
        draw.text((width - w - 40, height - h - 30), user_text, font=small_font, fill=(220, 220, 220, 200))

    # finalize to JPEG bytes
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=88)
    out.seek(0)
    return out.read()

async def make_and_send_thumbnail(message: Message, lines: List[str], caption_text: str):
    try:
        # prepare username display
        uname = ""
        uid = None
        try:
            if message.from_user:
                uid = message.from_user.id
                uname = message.from_user.first_name or ""
                if message.from_user.last_name:
                    uname += " " + message.from_user.last_name
        except Exception:
            uname = ""
        uname = (uname or "VISHAL").strip()

        # Run image generation in thread
        img_bytes = await asyncio.to_thread(generate_thumbnail, lines, uname)

        # send as photo with caption and a download button
        bot_username = app.username or "VISHALMUSIC_BOT"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✦ ᴅᴏᴡɴʟᴏᴀᴅ ɪᴍᴀɢᴇ", url=f"https://t.me/{bot_username}")]]
        )

        # caption_text is expected to contain HTML-safe mention if needed
        await message.reply_photo(photo=img_bytes, caption=caption_text, reply_markup=kb, disable_notification=True, parse_mode="html")
    except Exception as e:
        # fallback: simple text reply including username
        uname_safe = html.escape(uname if uname else "VISHAL")
        await message.reply_text(f"{html.escape(caption_text)}\n\n— {uname_safe}\n\n(⚠️ Thumbnail generator error: {e})")

def build_caption_and_lines(kind: str, display_name_html: str):
    # Returns lines for thumbnail and caption text, PERSONALIZED by embedding the username in the decorative line.
    # display_name_html should be HTML-escaped (or an <a> mention link) because caption will be sent with parse_mode="html".
    if kind == "goodnight":
        lines = [
            "❖ ɢᴏᴏᴅ ɴɪɢʜᴛ ❖",
            "sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs",
        ]
        caption = (
            "❖ ɢᴏᴏᴅ ɴɪɢʜᴛ ❖ sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs\n\n"
            f"❍   𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ 💤\n\n"
            "❖ ɢᴏ ᴛᴏ ➥ sʟᴇᴇᴘ ᴇᴀʀʟʏ"
        )
    else:  # good morning
        lines = [
            "☀️ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️",
            "ʜᴀᴠᴇ ᴀ ʙʀɪɢʜᴛ ᴅᴀʏ",
        ]
        caption = (
            "☀️ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️\n\n"
            f"❍   𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ ☕\n\n"
            "❖ ᴘʀᴀʏ ғᴏʀ ᴀ ɢᴏᴏᴅ ᴅᴀʏ"
        )
    return lines, caption

# Main message handler (regex detection)
@app.on_message(filters.text & ~filters.command(["goodnight", "goodmorning"]))
async def greet_detector_handler(client, message: Message):
    text = message.text or ""
    # get message time in configured timezone
    try:
        msg_dt = message.date  # Pyrogram message.date is UTC naive or tz-aware
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except Exception:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

    is_gn = bool(GOODNIGHT_RE.search(text))
    is_gm = bool(GOODMORNING_RE.search(text))

    # If both matches (rare), prefer night if current time is night
    if is_gn and is_gm:
        if is_good_night(local_dt):
            is_gm = False
        else:
            is_gn = False

    # get sender name for personalization
    uname = ""
    uid = None
    try:
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
    except Exception:
        uname = ""
    uname = uname.strip() or "VISHAL"

    # build an HTML-safe mention to embed in the decorative line
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
    else:
        display_html = html.escape(uname)

    # Act accordingly
    if is_gn:
        # Time check
        if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodnight", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            # friendly note
            await message.reply_text(f"✨ {html.escape(uname)}, ye time thoda jaldi/der ho sakta hai, par phir bhi — ɢᴏᴏᴅ ɴɪɢʜᴛ! 🌙")
    elif is_gm:
        if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodmorning", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(f"🌤️ {html.escape(uname)}, abhi 'morning' ka exact time nahi hai, phir bhi — ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ!")
    # else: do nothing (not a greeting)

# Optional explicit commands
@app.on_message(filters.command("goodnight"))
async def cmd_goodnight(client, message: Message):
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except Exception:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

    uname = ""
    uid = None
    try:
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
    except Exception:
        uname = ""
    uname = uname.strip() or "VISHAL"

    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
    else:
        display_html = html.escape(uname)

    if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
        lines, caption = build_caption_and_lines("goodnight", display_html)
        await make_and_send_thumbnail(message, lines, caption)
    else:
        await message.reply_text(f"{html.escape(uname)}, abhi night time nahi hai, par aap chaho toh main fir bhi bhej doon. /goodnight")

@app.on_message(filters.command("goodmorning"))
async def cmd_goodmorning(client, message: Message):
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except Exception:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

    uname = ""
    uid = None
    try:
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
    except Exception:
        uname = ""
    uname = uname.strip() or "VISHAL"

    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
    else:
        display_html = html.escape(uname)

    if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
        lines, caption = build_caption_and_lines("goodmorning", display_html)
        await make_and_send_thumbnail(message, lines, caption)
    else:
        await message.reply_text(f"{html.escape(uname)}, abhi morning ka time nahi hai — lekin /goodmorning se aap kabhi bhi bhej sakte ho.")
