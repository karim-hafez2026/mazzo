# Video Download Bot 🎥

أخف بوت تيليجرام لتحميل الفيديوهات من:
- YouTube ✅
- TikTok (بدون علامة مائية) ✅
- Facebook ✅
- Instagram ✅
- Twitter/X ✅
- أي موقع ✅

## التشغيل

1. **ركب المكتبات:**
```bash
cd ~/Desktop/video-dl-bot
pip install -r requirements.txt
```

2. **افتح bot.py وغير البيانات:**
   - `API_ID` و `API_HASH` من https://my.telegram.org/apps
   - `BOT_TOKEN` من @BotFather
   - `OWNER_ID` (اختياري) عشان تشوف `/stats`

3. **شغل البوت:**
```bash
python bot.py
```

## RAM
- **50-80MB** 🔥 يشتغل على 128MB بسلاسة
- للمقارنة: uploader-bot-v4 يستهلك 120MB+

## ملاحظات
- تيك توك بينزل بدون علامة مائية تلقائياً
- حد الرفع 49MB (حد تيليجرام)
- الفيديوهات الكبيرة جداً بتتخطى تلقائياً
