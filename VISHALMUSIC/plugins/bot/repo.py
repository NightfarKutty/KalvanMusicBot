from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from VISHALMUSIC import app
from config import BOT_USERNAME

repo_caption = """**
🚀 ᴄʟᴏɴᴇ ᴀɴᴅ ᴅᴇᴘʟᴏʏ – 🚀

➤ ᴅᴇᴘʟᴏʏ ᴇᴀsɪʟʏ ᴏɴ ʜᴇʀᴏᴋᴜ ᴡɪᴛʜᴏᴜᴛ ᴇʀʀᴏʀꜱ  
➤ ɴᴏ ʜᴇʀᴏᴋᴜ ʙᴀɴ ɪꜱꜱᴜᴇ  
➤ ɴᴏ ɪᴅ ʙᴀɴ ɪꜱꜱᴜᴇ   
➤ ᴜɴʟɪᴍɪᴛᴇᴅ ᴅʏɴᴏꜱ  
➤ ʀᴜɴ 24/7 ʟᴀɢ ꜰʀᴇᴇ

ɪꜰ ʏᴏᴜ ꜰᴀᴄᴇ ᴀɴʏ ᴘʀᴏʙʟᴇᴍ, ꜱᴇɴᴅ ꜱꜱ ɪɴ ꜱᴜᴘᴘᴏʀᴛ
**"""

@app.on_message(filters.command("repo"))
async def show_repo(_, msg):
    buttons = [
        [InlineKeyboardButton("· ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ ·", url=f"https://t.me/JennaMusicBot?startgroup=true")],
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
