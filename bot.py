"""
🎥 Video Download Bot - Telethon + yt-dlp
Lightweight | 50-80MB RAM | يشتغل على 128MB
"""
import os
import re
import asyncio
import shutil
import threading
import uuid
import aiohttp
from http.server import HTTPServer, BaseHTTPRequestHandler
from tempfile import mkdtemp
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument
import yt_dlp

# ====== التكوين ======
API_ID = int(os.environ.get("API_ID", 0))          # من my.telegram.org
API_HASH = os.environ.get("API_HASH", "")       # من my.telegram.org
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")      # من @BotFather
MAX_SIZE_MB = 49    # حد تيليجرام 50MB، بنحط 49 عشان نضمن
OWNER_ID = int(os.environ.get("OWNER_ID", 0))        # معرفك (optionnel)

# ====== الإعدادات ======
DOWNLOAD_DIR = mkdtemp(prefix="ytdl_")
bot = TelegramClient('video_bot', API_ID, API_HASH)

# Regex لاكتشاف الروابط
URL_PATTERN = re.compile(r'https?://[^\s]+')


async def progress_callback(current, total, event, msg):
    """إظهار进度 التحميل"""
    if total > 0:
        percent = (current * 100) // total
        if percent % 10 == 0:  # كل 10%
            try:
                await msg.edit(f"📥 جاري التحميل... {percent}%")
            except:
                pass


async def download_via_cobalt(url: str) -> dict:
    """تحميل الفيديو باستخدام Cobalt API كحل أساسي"""
    # API v1 (new format as of 2024)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {"url": url, "videoQuality": "1080", "filenameStyle": "basic"}
    
    cobalt_instances = [
        "https://api.cobalt.tools/",
        "https://cobalt.api.timelessnesses.me/",
        "https://co.wuk.sh/",
    ]
    
    for instance in cobalt_instances:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    instance, json=data, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        continue
                    result = await resp.json()
                    
                    status = result.get('status', '')
                    if status == 'error':
                        continue
                    
                    # status can be 'stream', 'redirect', or 'tunnel'
                    download_url = result.get('url')
                    if not download_url:
                        continue
                    
                    filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    
                    async with session.get(
                        download_url,
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as file_resp:
                        if file_resp.status != 200:
                            continue
                        
                        with open(filepath, 'wb') as f:
                            async for chunk in file_resp.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                    
                    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                        continue
                    
                    filesize = os.path.getsize(filepath)
                    return {
                        'path': filepath,
                        'title': result.get('filename', 'video'),
                        'filesize': filesize,
                        'ext': 'mp4',
                        'duration': 0,
                    }
        except Exception:
            continue
    
    return {'error': '❌ Cobalt فشل على كل الـ instances'}


async def download_via_ytdlp(url: str) -> dict:
    """التحميل الاحتياطي باستخدام yt-dlp"""
    cookie_file = os.path.join(os.path.dirname(__file__), 'cookies.txt')

    base_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'max_filesize': MAX_SIZE_MB * 1024 * 1024,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file if os.path.exists(cookie_file) else None,
        # Bypass 403 / bot-detection
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }

    # Try multiple strategies in order
    strategies = [
        # 1. iOS client — works for most YouTube videos
        {**base_opts,
         'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
         'extractor_args': {'youtube': {'player_client': ['ios']}}},
        # 2. Android client
        {**base_opts,
         'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
         'extractor_args': {'youtube': {'player_client': ['android']}}},
        # 3. Web client (default) — last resort
        {**base_opts,
         'format': 'best[filesize<50M]/best'},
    ]

    last_error = '❌ فشل التحميل'
    for opts in strategies:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    continue

                filepath = ydl.prepare_filename(info)
                # yt-dlp أحياناً يغير الامتداد بعد merge
                if not os.path.exists(filepath):
                    for f in os.listdir(DOWNLOAD_DIR):
                        if info.get('id', '') in f:
                            filepath = os.path.join(DOWNLOAD_DIR, f)
                            break

                if not os.path.exists(filepath):
                    continue

                return {
                    'path': filepath,
                    'title': info.get('title', 'Video'),
                    'duration': info.get('duration', 0),
                    'filesize': os.path.getsize(filepath),
                    'ext': info.get('ext', 'mp4'),
                    'webpage_url': info.get('webpage_url', url),
                }
        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if 'filesize' in err.lower():
                return {'error': f'⚠️ الفيديو أكبر من {MAX_SIZE_MB}MB'}
            last_error = f'❌ فشل التحميل: {err[:120]}'
            continue
        except Exception as e:
            last_error = f'❌ خطأ: {str(e)[:120]}'
            continue

    return {'error': last_error}


async def download_video(url: str) -> dict:
    """المدير الأساسي للتحميل: يجرب Cobalt أولاً ثم yt-dlp"""
    cobalt_res = await download_via_cobalt(url)
    if 'error' not in cobalt_res:
        return cobalt_res
    
    print(f"Cobalt failed: {cobalt_res.get('error')}. Falling back to yt-dlp...")
    return await download_via_ytdlp(url)


@bot.on(events.NewMessage(pattern=URL_PATTERN))
async def handle_link(event):
    """استقبال الرابط والتحميل"""
    url = re.search(URL_PATTERN, event.message.text).group()
    
    msg = await event.reply("🔍 جاري معالجة الرابط...")
    
    result = await download_video(url)
    
    if 'error' in result:
        await msg.edit(result['error'])
        return
    
    filepath = result['path']
    if not filepath or not os.path.exists(filepath):
        await msg.edit("❌ الملف مش موجود بعد التحميل")
        return
    
    filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
    
    if filesize_mb > MAX_SIZE_MB:
        os.remove(filepath)
        await msg.edit(f"⚠️ الفيديو كبير جداً ({filesize_mb:.0f}MB)\nأقصى حد {MAX_SIZE_MB}MB")
        return
    
    await msg.edit(f"📤 جاري الرفع... ({filesize_mb:.1f}MB)")
    
    try:
        caption = f"<b>{result['title'][:50]}</b>"
        if result.get('duration'):
            mins, secs = divmod(result['duration'], 60)
            caption += f"\n⏱ {int(mins)}:{int(secs):02d}"
        caption += f"\n🔗 {url[:40]}..."
        
        await event.reply(
            file=filepath,
            message=caption,
            parse_mode='html'
        )
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ فشل الرفع: {str(e)[:80]}")
    finally:
        # تنظيف
        try:
            os.remove(filepath)
        except:
            pass


@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🎥 <b>Video Download Bot</b>\n\n"
        "ارسلي رابط فيديو من:\n"
        "• YouTube\n• TikTok (بدون علامة مائية)\n"
        "• Facebook\n• Instagram\n"
        "• Twitter/X\n• وأي موقع تاني\n\n"
        "⚡ سريع وخفيف",
        parse_mode='html'
    )


@bot.on(events.NewMessage(pattern='/stats'))
async def stats(event):
    if event.sender_id == OWNER_ID or OWNER_ID == 0:
        import psutil
        process = psutil.Process(os.getpid())
        ram = process.memory_info().rss / 1024 / 1024
        await event.reply(f"📊 RAM: {ram:.1f}MB")


async def cleanup():
    """تنظيف الملفات المؤقتة عند الإغلاق"""
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass  # silence HTTP logs


def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

async def main():
    print("🚀 Bot is running...")
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Health check server started")
    
    await bot.start(bot_token=BOT_TOKEN)
    
    print('✅ Video Download Bot شغال!')
    
    await bot.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.run(cleanup())
