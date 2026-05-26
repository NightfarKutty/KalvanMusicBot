import os
import io
import re
import random
import asyncio
import datetime
import html
from zoneinfo import ZoneInfo
from typing import List

from pyrogram import filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageFilter
)

from VISHALMUSIC import app

# =========================================================
# CONFIG
# =========================================================

TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")

FONT_PATH = os.environ.get(
    "FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)

ALLOW_OUT_OF_TIME_REPLY = bool(
    os.environ.get("ALLOW_OUT_OF_TIME_REPLY", "").strip()
)

# =========================================================
# RANDOM TEXTS
# =========================================================

GOOD_MORNING_LINES = [
    ["☀️ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️", "ʜᴀᴠᴇ ᴀ ʙᴇᴀᴜᴛɪғᴜʟ ᴅᴀʏ"],
    ["🌤️ ʀɪsᴇ ᴀɴᴅ sʜɪɴᴇ 🌤️", "sᴍɪʟᴇ ᴀɴᴅ sᴛᴀʏ ʜᴀᴘᴘʏ"],
    ["🌸 ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 🌸", "ɴᴇᴡ ᴅᴀʏ ɴᴇᴡ ʜᴏᴘᴇ"],
    ["✨ ᴍᴏʀɴɪɴɢ ᴠɪʙᴇs ✨", "ᴇɴᴊᴏʏ ᴛʜᴇ ᴅᴀʏ"],
    ["☕ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☕", "sᴛᴀʏ ᴘᴏsɪᴛɪᴠᴇ"]
]

GOOD_NIGHT_LINES = [
    ["🌙 ɢᴏᴏᴅ ɴɪɢʜᴛ 🌙", "sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs"],
    ["✨ ɴɪɢʜᴛ ᴠɪʙᴇs ✨", "sʟᴇᴇᴘ ᴘᴇᴀᴄᴇғᴜʟʟʏ"],
    ["🌌 ɢᴏᴏᴅ ɴɪɢʜᴛ 🌌", "ʀᴇsᴛ ᴡᴇʟʟ"],
    ["💫 sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs 💫", "ʜᴀᴠᴇ ᴀ ɢᴏᴏᴅ sʟᴇᴇᴘ"],
    ["🌃 ɴɪɢʜᴛ ɴɪɢʜᴛ 🌃", "ᴛᴀᴋᴇ ᴄᴀʀᴇ"]
]

# =========================================================
# GREETING DETECTORS
# =========================================================

GOODNIGHT_RE = re.compile(
    r"\b(good\s*night|goodnight|gn|nighty|nite)\b",
    re.IGNORECASE
)

GOODMORNING_RE = re.compile(
    r"\b(good\s*morning|goodmorning|gm|morning|subah)\b",
    re.IGNORECASE
)

# =========================================================
# TIME CHECK
# =========================================================

def is_good_morning(dt_local):
    return 4 <= dt_local.hour < 12

def is_good_night(dt_local):
    return dt_local.hour >= 20 or dt_local.hour < 4

# =========================================================
# FONT
# =========================================================

def load_font(size):
    try:
        if FONT_PATH and os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()

# =========================================================
# RANDOM NATURE BACKGROUND
# =========================================================

def create_random_nature_background(width, height):
    themes = [
        ((135, 206, 235), (255, 183, 77)),   # sky sunrise
        ((34, 139, 34), (144, 238, 144)),    # forest
        ((25, 25, 112), (72, 61, 139)),      # night
        ((70, 130, 180), (176, 224, 230)),   # ocean
        ((255, 140, 0), (255, 215, 0)),      # sunset
        ((46, 139, 87), (152, 251, 152))     # green land
    ]

    top, bottom = random.choice(themes)

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Gradient
    for y in range(height):
        ratio = y / height
        r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
        g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
        b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Random circles for artistic look
    for _ in range(40):
        x = random.randint(0, width)
        y = random.randint(0, height)
        radius = random.randint(20, 120)
        color = (
            random.randint(150, 255),
            random.randint(150, 255),
            random.randint(150, 255)
        )
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=color
        )

    img = img.filter(ImageFilter.GaussianBlur(18))
    return img

# =========================================================
# IMAGE GENERATOR
# =========================================================

def generate_thumbnail(lines, username=""):
    width = 1280
    height = 720

    img = create_random_nature_background(width, height)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 70))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    title_font = load_font(70)
    sub_font = load_font(42)
    small_font = load_font(30)

    fonts = [title_font if i == 0 else sub_font for i in range(len(lines))]

    total_height = 0
    sizes = []

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=fonts[i])
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        sizes.append((w, h))
        total_height += h + 25

    y = (height - total_height) // 2

    for i, line in enumerate(lines):
        w, h = sizes[i]
        x = (width - w) // 2
        # Shadow
        draw.text((x + 4, y + 4), line, font=fonts[i], fill=(0, 0, 0))
        # Main
        draw.text((x, y), line, font=fonts[i], fill=(255, 255, 255))
        y += h + 25

    # Username
    if username:
        user_text = f"— {username}"
        bbox = draw.textbbox((0, 0), user_text, font=small_font)
        uw = bbox[2] - bbox[0]
        uh = bbox[3] - bbox[1]
        draw.text((width - uw - 40, height - uh - 30), user_text, font=small_font, fill=(255, 255, 255))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=95)
    out.seek(0)
    return out.read()

# =========================================================
# SEND PHOTO
# =========================================================

async def make_and_send_thumbnail(message, lines, caption):
    try:
        uname = "User"
        if message.from_user:
            uname = message.from_user.first_name or "User"

        img_bytes = await asyncio.to_thread(generate_thumbnail, lines, uname)
        photo = io.BytesIO(img_bytes)
        photo.name = "greeting.jpg"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌸 ᴊᴏɪɴ 🌸", url=f"https://t.me/{app.username or ''}")]
        ])

        await message.reply_photo(photo=photo, caption=caption, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        await message.reply_text(f"⚠️ Error:\n{e}")

# =========================================================
# MAIN HANDLER - FIXED: Added proper filters and error handling
# =========================================================

@app.on_message(filters.text & ~filters.command(["goodmorning", "goodnight"]))  # Don't trigger on commands
async def greet_detector_handler(client, message: Message):
    # Skip if message is from a channel or has no text
    if not message.text or message.sender_chat:
        return
    
    # Skip if message is a command
    if message.text.startswith('/'):
        return
    
    text = message.text or ""

    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except Exception:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

    is_gn = bool(GOODNIGHT_RE.search(text))
    is_gm = bool(GOODMORNING_RE.search(text))

    # Skip if no greeting detected
    if not is_gn and not is_gm:
        return

    uname = "User"
    uid = None

    if message.from_user:
        uid = message.from_user.id
        uname = message.from_user.first_name or "User"

    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
    else:
        display_html = html.escape(uname)

    # GOOD MORNING
    if is_gm:
        if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines = random.choice(GOOD_MORNING_LINES)
            caption = f"{lines[0]}\n\n❍ 𐙚 ꒷꒦ ๋{display_html} ☕\n\n{lines[1]}"
            await make_and_send_thumbnail(message, lines, caption)

    # GOOD NIGHT
    elif is_gn:
        if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines = random.choice(GOOD_NIGHT_LINES)
            caption = f"{lines[0]}\n\n❍ 𐙚 ꒷꒦ ๋{display_html} 🌙\n\n{lines[1]}"
            await make_and_send_thumbnail(message, lines, caption)

# =========================================================
# COMMANDS - These won't block other commands
# =========================================================

@app.on_message(filters.command("goodmorning"))
async def cmd_gm(client, message: Message):
    lines = random.choice(GOOD_MORNING_LINES)
    uid = message.from_user.id
    uname = message.from_user.first_name
    display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
    caption = f"{lines[0]}\n\n{display_html}\n\n{lines[1]}"
    await make_and_send_thumbnail(message, lines, caption)

@app.on_message(filters.command("goodnight"))
async def cmd_gn(client, message: Message):
    lines = random.choice(GOOD_NIGHT_LINES)
    uid = message.from_user.id
    uname = message.from_user.first_name
    display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
    caption = f"{lines[0]}\n\n{display_html}\n\n{lines[1]}"
    await make_and_send_thumbnail(message, lines, caption)
