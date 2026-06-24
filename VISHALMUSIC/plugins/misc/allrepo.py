from pyrogram import Client, filters
from pyrogram.types import Message
import httpx
from VISHALMUSIC import app


def chunk_string(text, chunk_size):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


repo_caption = """**
🚀 ʀᴇᴩᴏ ᴀɴᴅ ᴅᴇᴘʟᴏʏ – 🚀

➤ ᴅᴇᴘʟᴏʏ ᴇᴀsɪʟʏ ᴏɴ ʜᴇʀᴏᴋᴜ ᴡɪᴛʜᴏᴜᴛ ᴇʀʀᴏʀꜱ  
➤ ɴᴏ ʜᴇʀᴏᴋᴜ ʙᴀɴ ɪꜱꜱᴜᴇ  
➤ ɴᴏ ɪᴅ ʙᴀɴ ɪꜱꜱᴜᴇ   
➤ ᴜɴʟɪᴍɪᴛᴇᴅ ᴅʏɴᴏꜱ  
➤ ʀᴜɴ 24/7 ʟᴀɢ ꜰʀᴇᴇ

ɪꜰ ʏᴏᴜ ꜰᴀᴄᴇ ᴀɴʏ ᴘʀᴏʙʟᴇᴍ, ꜱᴇɴᴅ ꜱꜱ ɪɴ ꜱᴜᴘᴘᴏʀᴛ
**"""

@app.on_message(filters.command("allrepo"))
async def show_repo(_, msg):
    buttons = [
        [InlineKeyboardButton("· ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ ·", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("ɴꜰᴛ ɴᴇᴛᴡᴏʀᴋ", url="https://t.me/NightFarBots"),
            InlineKeyboardButton("ʙᴜʏ ʀᴇᴩᴏ", url="https://t.me/KuttyHacker")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    try:  
        await msg.reply_photo(
            photo="https://i.ibb.co/mrHqmZ4Z/x.jpg",
            caption=repo_caption,
            reply_markup=reply_markup
        )
    except:
        pass
