import os
import io
import re
import random
import math
import asyncio
import html
from zoneinfo import ZoneInfo
from typing import List
from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from VISHALMUSIC import app

# ============ CONFIGURATION ============
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
FONT_PATH = os.environ.get("FONT_PATH", "")
ALLOW_OUT_OF_TIME_REPLY = bool(os.environ.get("ALLOW_OUT_OF_TIME_REPLY", "false").strip())

# ============ GREETING PATTERNS ============
GOODNIGHT_RE = re.compile(r"\b(good\s*night|goodnight|gn|nighty|nite|g night|gud night)\b", re.IGNORECASE)
GOODMORNING_RE = re.compile(r"\b(good\s*morning|goodmorning|gm|morning|subah|gud morning|g morning)\b", re.IGNORECASE)

# ============ TIME CHECK FUNCTIONS ============
def is_good_morning(dt_local) -> bool:
    return 4 <= dt_local.hour < 12

def is_good_night(dt_local) -> bool:
    return dt_local.hour >= 20 or dt_local.hour < 4

# ============ SPECIAL THUMBNAIL GENERATOR ============
def generate_thumbnail(lines: List[str], username: str = "", width: int = 1280, height: int = 720) -> bytes:
    # Create base image
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    
    # Check if it's night or morning theme
    is_night = "goodnight" in str(lines).lower()
    
    # Beautiful gradient background
    if is_night:
        # Night theme - deep blue to purple to dark
        colors = [(10, 20, 50), (40, 20, 70), (80, 30, 100), (60, 20, 80)]
    else:
        # Morning theme - orange to yellow to light orange
        colors = [(255, 120, 50), (255, 180, 70), (255, 220, 100), (255, 200, 80)]
    
    # Create smooth gradient
    for y in range(height):
        ratio = y / (height - 1)
        if ratio < 0.33:
            r = int(colors[0][0] * (1 - ratio*3) + colors[1][0] * (ratio*3))
            g = int(colors[0][1] * (1 - ratio*3) + colors[1][1] * (ratio*3))
            b = int(colors[0][2] * (1 - ratio*3) + colors[1][2] * (ratio*3))
        elif ratio < 0.66:
            r2 = (ratio - 0.33) * 3
            r = int(colors[1][0] * (1 - r2) + colors[2][0] * r2)
            g = int(colors[1][1] * (1 - r2) + colors[2][1] * r2)
            b = int(colors[1][2] * (1 - r2) + colors[2][2] * r2)
        else:
            r2 = (ratio - 0.66) * 3
            r = int(colors[2][0] * (1 - r2) + colors[3][0] * r2)
            g = int(colors[2][1] * (1 - r2) + colors[3][1] * r2)
            b = int(colors[2][2] * (1 - r2) + colors[3][2] * r2)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Add stars for night theme
    if is_night:
        random.seed(42)
        for _ in range(200):
            x = random.randint(0, width)
            y = random.randint(0, height // 2)
            size = random.randint(1, 3)
            brightness = random.randint(150, 255)
            draw.ellipse([(x, y), (x + size, y + size)], fill=(brightness, brightness, brightness))
        
        # Add some bigger stars with glow
        for _ in range(20):
            x = random.randint(0, width)
            y = random.randint(0, height // 3)
            size = random.randint(3, 6)
            draw.ellipse([(x, y), (x + size, y + size)], fill=(255, 255, 200))
    
    # Decorative border
    border_width = 10
    border_color = (255, 215, 0) if not is_night else (100, 150, 255)
    for i in range(border_width):
        alpha = 255 - (i * 20)
        draw.rectangle([(i, i), (width - i, height - i)], outline=border_color, width=1)
    
    # Corner decorations
    corner_size = 100
    for x, y in [(0, 0), (width - corner_size, 0), (0, height - corner_size), (width - corner_size, height - corner_size)]:
        # Draw corner curves
        draw.arc([(x, y), (x + corner_size, y + corner_size)], 0, 90, fill=border_color, width=8)
        draw.line([(x + 20, y), (x + corner_size - 20, y)], fill=border_color, width=5)
        draw.line([(x, y + 20), (x, y + corner_size - 20)], fill=border_color, width=5)
    
    # Main content box with rounded corners
    box_margin = 80
    box = [box_margin, box_margin, width - box_margin, height - box_margin]
    
    # Create rounded rectangle
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    
    def rounded_rect(draw, xy, radius, fill):
        x1, y1, x2, y2 = xy
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.ellipse([x1, y1, x1 + radius*2, y1 + radius*2], fill=fill)
        draw.ellipse([x2 - radius*2, y1, x2, y1 + radius*2], fill=fill)
        draw.ellipse([x1, y2 - radius*2, x1 + radius*2, y2], fill=fill)
        draw.ellipse([x2 - radius*2, y2 - radius*2, x2, y2], fill=fill)
    
    rounded_rect(od, box, 50, (0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    def load_font(size: int, bold: bool = False):
        try:
            if FONT_PATH and os.path.exists(FONT_PATH):
                return ImageFont.truetype(FONT_PATH, size)
            
            font_options = []
            if bold:
                font_options = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                    "/System/Library/Fonts/Helvetica-Bold.ttf",
                    "C:\\Windows\\Fonts\\ArialBD.ttf",
                    "C:\\Windows\\Fonts\\SegoeUI-Bold.ttf"
                ]
            else:
                font_options = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    "/System/Library/Fonts/Helvetica.ttf",
                    "C:\\Windows\\Fonts\\Arial.ttf",
                    "C:\\Windows\\Fonts\\SegoeUI.ttf"
                ]
            
            for font_path in font_options:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
        except Exception:
            pass
        return ImageFont.load_default()
    
    # Draw main content
    title_font = load_font(110, True)
    sub_font = load_font(60, False)
    small_font = load_font(40, False)
    
    center_x = width // 2
    
    # Calculate text positions
    line_data = []
    total_height = 0
    
    for i, line in enumerate(lines):
        font = title_font if i == 0 else sub_font
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_data.append((line, font, w, h))
        total_height += h + 40
    
    start_y = (height - total_height) // 2
    current_y = start_y
    
    # Draw text with glow effect
    for idx, (line, font, w, h) in enumerate(line_data):
        x = center_x - w // 2
        
        # Glow effect
        for offset in range(5, 0, -1):
            alpha = 100 - offset * 15
            if idx == 0:
                draw.text((x - offset, current_y - offset), line, font=font, fill=(255, 220, 100, alpha))
            else:
                draw.text((x - offset, current_y - offset), line, font=font, fill=(255, 200, 100, alpha))
        
        # Main text color
        if idx == 0:
            if is_night:
                text_color = (150, 200, 255)
            else:
                text_color = (255, 220, 100)
        else:
            text_color = (255, 240, 180)
        
        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += h + 40
    
    # Decorative line
    sep_y = current_y + 30
    if sep_y < height - 150:
        line_y = sep_y
        for i in range(3):
            y_pos = line_y + (i * 5)
            gradient_start = (center_x - 250, y_pos)
            gradient_end = (center_x + 250, y_pos)
            for step in range(500):
                step_x = gradient_start[0] + step
                if step_x <= gradient_end[0]:
                    ratio = step / 500
                    if is_night:
                        color = (100 + int(155 * ratio), 100 + int(100 * ratio), 255)
                    else:
                        color = (255, 150 + int(70 * ratio), 50 + int(50 * ratio))
                    draw.point((step_x, y_pos), fill=color)
    
    # Draw username with style
    if username:
        user_text = f"⭐ {username} ⭐"
        bbox = draw.textbbox((0, 0), user_text, font=small_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        # Background for username
        bg_padding = 25
        bg_x1 = width - w - 80 - bg_padding
        bg_y1 = height - h - 60 - bg_padding
        bg_x2 = width - 40 + bg_padding
        bg_y2 = height - 20 + bg_padding
        
        draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=(0, 0, 0, 150), outline=border_color, width=3)
        draw.text((width - w - 80, height - h - 60), user_text, font=small_font, fill=(255, 215, 0))
    
    # Add special graphics
    if is_night:
        # Add moon
        moon_center = (120, 120)
        moon_radius = 50
        draw.ellipse([(moon_center[0] - moon_radius, moon_center[1] - moon_radius),
                      (moon_center[0] + moon_radius, moon_center[1] + moon_radius)], 
                     fill=(240, 240, 200))
        # Moon crater
        draw.ellipse([(moon_center[0] - 15, moon_center[1] - 10),
                      (moon_center[0] + 5, moon_center[1] + 15)], fill=(200, 200, 160))
        draw.ellipse([(moon_center[0] + 15, moon_center[1] - 20),
                      (moon_center[0] + 30, moon_center[1] - 5)], fill=(200, 200, 160))
    else:
        # Add sun
        sun_center = (width - 120, 120)
        sun_radius = 55
        
        # Sun rays
        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            x1 = sun_center[0] + math.cos(rad) * (sun_radius + 15)
            y1 = sun_center[1] + math.sin(rad) * (sun_radius + 15)
            x2 = sun_center[0] + math.cos(rad) * (sun_radius + 35)
            y2 = sun_center[1] + math.sin(rad) * (sun_radius + 35)
            draw.line([(x1, y1), (x2, y2)], fill=(255, 200, 50), width=5)
        
        draw.ellipse([(sun_center[0] - sun_radius, sun_center[1] - sun_radius),
                      (sun_center[0] + sun_radius, sun_center[1] + sun_radius)], 
                     fill=(255, 220, 80), outline=(255, 180, 50), width=4)
        
        # Sun face
        draw.ellipse([(sun_center[0] - 20, sun_center[1] - 15),
                      (sun_center[0] - 5, sun_center[1] - 5)], fill=(255, 140, 50))
        draw.ellipse([(sun_center[0] + 5, sun_center[1] - 15),
                      (sun_center[0] + 20, sun_center[1] - 5)], fill=(255, 140, 50))
        draw.arc([(sun_center[0] - 20, sun_center[1] - 5),
                  (sun_center[0] + 20, sun_center[1] + 20)], 0, 180, fill=(255, 140, 50), width=4)
    
    # Save image
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=92, optimize=True)
    output.seek(0)
    return output.read()

# ============ SEND THUMBNAIL FUNCTION ============
async def make_and_send_thumbnail(message: Message, lines: List[str], caption_text: str):
    try:
        # Get username
        uname = ""
        uid = None
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
        
        if not uname.strip():
            uname = "Dear User"
        
        # Generate image in thread
        img_bytes = await asyncio.to_thread(generate_thumbnail, lines, uname)
        
        # Create button
        button = InlineKeyboardMarkup([[
            InlineKeyboardButton("✨ Download ✨", url=f"https://t.me/{app.username or 'VISHALMUSIC'}")
        ]])
        
        # Send photo
        await message.reply_photo(
            photo=img_bytes,
            caption=caption_text,
            reply_markup=button,
            parse_mode="html"
        )
    except Exception as e:
        # Fallback
        safe_name = html.escape(uname if uname else "User")
        await message.reply_text(
            f"{caption_text}\n\n— {safe_name}\n\n⚠️ Image error: {str(e)[:50]}",
            parse_mode="html"
        )

# ============ CAPTION BUILDER ============
def build_caption_and_lines(kind: str, display_name_html: str):
    if kind == "goodnight":
        lines = ["❖ GOOD NIGHT ❖", "SWEET DREAMS"]
        caption = (
            "❖ ɢᴏᴏᴅ ɴɪɢʜᴛ ❖ sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs\n\n"
            f"❍   𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ 💤\n\n"
            "❖ ɢᴏ ᴛᴏ ➥ sʟᴇᴇᴘ ᴇᴀʀʟʏ"
        )
    else:
        lines = ["☀️ GOOD MORNING ☀️", "HAVE A BRIGHT DAY"]
        caption = (
            "☀️ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️\n\n"
            f"❍   𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ ☕\n\n"
            "❖ ᴘʀᴀʏ ғᴏʀ ᴀ ɢᴏᴏᴅ ᴅᴀʏ"
        )
    return lines, caption

# ============ MAIN HANDLER ============
@app.on_message(filters.text & ~filters.command(["goodnight", "goodmorning", "gn", "gm"]))
async def greet_detector_handler(client, message: Message):
    text = message.text or ""
    
    # Get local time
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))
    
    is_gn = bool(GOODNIGHT_RE.search(text))
    is_gm = bool(GOODMORNING_RE.search(text))
    
    # Handle both matches
    if is_gn and is_gm:
        if is_good_night(local_dt):
            is_gm = False
        else:
            is_gn = False
    
    if not (is_gn or is_gm):
        return
    
    # Get user info
    uname = ""
    uid = None
    if message.from_user:
        uid = message.from_user.id
        uname = message.from_user.first_name or ""
        if message.from_user.last_name:
            uname += " " + message.from_user.last_name
    
    if not uname.strip():
        uname = "User"
    
    # Create mention
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname[:30])}</a>"
    else:
        display_html = html.escape(uname)
    
    # Send response
    if is_gn:
        if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodnight", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(
                f"✨ {html.escape(uname)}, abhi raat ka time nahi hai, phir bhi - ɢᴏᴏᴅ ɴɪɢʜᴛ! 🌙",
                parse_mode="html"
            )
    elif is_gm:
        if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodmorning", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(
                f"🌤️ {html.escape(uname)}, abhi subah ka time nahi hai, phir bhi - ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ!",
                parse_mode="html"
            )

# ============ COMMAND HANDLERS ============
@app.on_message(filters.command(["goodnight", "gn"]))
async def cmd_goodnight(client, message: Message):
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))
    
    uname = ""
    uid = None
    if message.from_user:
        uid = message.from_user.id
        uname = message.from_user.first_name or ""
        if message.from_user.last_name:
            uname += " " + message.from_user.last_name
    
    if not uname.strip():
        uname = "User"
    
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname[:30])}</a>"
    else:
        display_html = html.escape(uname)
    
    if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
        lines, caption = build_caption_and_lines("goodnight", display_html)
        await make_and_send_thumbnail(message, lines, caption)
    else:
        await message.reply_text(
            f"{html.escape(uname)}, abhi night time nahi hai. Still, /goodnight",
            parse_mode="html"
        )

@app.on_message(filters.command(["goodmorning", "gm"]))
async def cmd_goodmorning(client, message: Message):
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))
    
    uname = ""
    uid = None
    if message.from_user:
        uid = message.from_user.id
        uname = message.from_user.first_name or ""
        if message.from_user.last_name:
            uname += " " + message.from_user.last_name
    
    if not uname.strip():
        uname = "User"
    
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname[:30])}</a>"
    else:
        display_html = html.escape(uname)
    
    if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
        lines, caption = build_caption_and_lines("goodmorning", display_html)
        await make_and_send_thumbnail(message, lines, caption)
    else:
        await message.reply_text(
            f"{html.escape(uname)}, abhi morning time nahi hai. Still, /goodmorning",
            parse_mode="html"
        )
