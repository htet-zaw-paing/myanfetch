import asyncio
import logging
import os
from pathlib import Path

import yt_dlp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramConflictError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger("youtube-bot")


TELE_BOT = os.getenv("TELE_BOT")
COOKIES_FILE = Path("cookies.txt")

if not TELE_BOT:
    raise ValueError("TELE_BOT environment variable is missing")


bot = Bot(token=TELE_BOT)
dp = Dispatcher()


class DownloadProcess(StatesGroup):
    url = State()


def prepare_cookies_file() -> None:
    """Create cookies.txt from the Render YOUTUBE_COOKIES variable."""
    cookies_text = os.getenv("YOUTUBE_COOKIES")

    if not cookies_text:
        print("YOUTUBE_COOKIES is not set; continuing without cookies", flush=True)
        return

    cookies_text = cookies_text.replace("\\r\\n", "\n").replace("\\n", "\n")
    COOKIES_FILE.write_text(cookies_text, encoding="utf-8")
    print(f"YouTube cookies file created: {COOKIES_FILE}", flush=True)


def download_mp3_sync(video_url: str, bitrate: str) -> dict:
    """Download the best available audio and convert it to MP3."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(id)s.%(ext)s",
        "source_address": "0.0.0.0",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "verbose": True,
        "retries": 3,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "sleep_interval_requests": 1,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(bitrate),
            }
        ],
    }

    if COOKIES_FILE.is_file() and COOKIES_FILE.stat().st_size > 0:
        ydl_opts["cookiefile"] = str(COOKIES_FILE)
        print("Using cookies.txt", flush=True)
    else:
        print("cookies.txt was not found or is empty", flush=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filepath = Path(f"{info['id']}.mp3")

        return {
            "filepath": filepath,
            "title": info.get("title", "Unknown Title"),
            "duration": info.get("duration") or 0,
            "uploader": info.get("uploader", "Unknown Artist"),
        }


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Hello! Send me a YouTube link to download it as MP3.")


@dp.message(F.text.startswith("http"))
async def handle_link(message: Message, state: FSMContext) -> None:
    await state.update_data(url=message.text.strip())

    builder = InlineKeyboardBuilder()
    builder.button(text="192 kbps (Standard)", callback_data="kbps_192")
    builder.button(text="320 kbps (High Quality)", callback_data="kbps_320")
    builder.adjust(1)

    await message.answer("Select quality:", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("kbps_"))
async def process_quality_selection(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.answer()

    user_data = await state.get_data()
    url = user_data.get("url")

    if not url:
        await callback.message.edit_text("Session expired. Please send the link again.")
        await state.clear()
        return

    bitrate = callback.data.split("_", 1)[1]
    await callback.message.edit_text(
        f"Downloading at {bitrate} kbps. Please wait..."
    )

    filepath: Path | None = None

    try:
        data = await asyncio.to_thread(download_mp3_sync, url, bitrate)
        filepath = Path(data["filepath"])

        await callback.message.answer_audio(
            audio=FSInputFile(filepath),
            title=data["title"],
            performer=data["uploader"],
            duration=data["duration"],
            caption=f"Downloaded successfully at {bitrate} kbps",
        )

        await callback.message.delete()

    except Exception as error:
        error_text = str(error).strip() or repr(error)
        logger.exception("Download failed")
        print(f"Download failed: {error_text}", flush=True)
        await callback.message.edit_text(
            "❌ Download failed.\n\n"
            f"Technical error:\n{error_text[:1200]}"
        )

    finally:
        if filepath and filepath.exists():
            filepath.unlink()
        await state.clear()


async def handle_ping(request: web.Request) -> web.Response:
    return web.Response(text="Bot is awake and running on Render!")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main() -> None:
    prepare_cookies_file()
    print(f"yt-dlp version: {yt_dlp.version.__version__}", flush=True)

    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    except TelegramConflictError:
        logger.critical(
            "Telegram rejected polling because another process is using this "
            "bot token. Stop the other instance before restarting Render."
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
