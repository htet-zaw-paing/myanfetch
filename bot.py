import asyncio
import os
import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web 

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class DownloadProcess(StatesGroup):
    url = State()

def download_mp3_sync(video_url: str, bitrate: str) -> dict:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': bitrate,
        }],
        'quiet': True,
        'noplaylist': True
    }
    
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filepath = f"{info['id']}.mp3"
        return {
            "filepath": filepath,
            "title": info.get('title', 'Unknown Title'),
            "duration": info.get('duration', 0),
            "uploader": info.get('uploader', 'Unknown Artist')
        }

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Hello! Send me a YouTube link to download it as MP3.")

@dp.message(F.text.startswith("http"))
async def handle_link(message: Message, state: FSMContext):
    await state.update_data(url=message.text)
    builder = InlineKeyboardBuilder()
    builder.button(text="192 kbps (Standard)", callback_data="kbps_192")
    builder.button(text="320 kbps (High Quality)", callback_data="kbps_320")
    builder.adjust(1)
    await message.answer("Select quality:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("kbps_"))
async def process_quality_selection(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_data = await state.get_data()
    url = user_data.get("url")
    if not url:
        return await callback.message.edit_text("Session expired. Please send the link again.")
        
    bitrate = callback.data.split("_")[1] 
    await callback.message.edit_text(f"🎧 Downloading at {bitrate} kbps... Please wait.")
    
    try:
        data = await asyncio.to_thread(download_mp3_sync, url, bitrate)
        filepath = data["filepath"]
        audio_file = FSInputFile(filepath)
        
        await callback.message.answer_audio(
            audio=audio_file, 
            title=data["title"], 
            performer=data["uploader"], 
            duration=data["duration"],
            caption=f"Downloaded successfully at {bitrate} kbps"
        )
        if os.path.exists(filepath): 
            os.remove(filepath)
        await callback.message.delete()
    except Exception as e:
        await callback.message.edit_text(f"❌ Error downloading: {str(e)}")
    finally:
        await state.clear()

async def handle_ping(request):
    return web.Response(text="Bot is awake and running on Render!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    cookies_text = os.getenv("YOUTUBE_COOKIES")
    if cookies_text:
        with open("cookies.txt", "w") as f:
            f.write(cookies_text)

    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
