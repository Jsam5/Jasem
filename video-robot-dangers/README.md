# خطورة الروبوتات — فيديو قصير

فيديو عربي مدته حوالي دقيقة عن مخاطر الروبوتات والذكاء الاصطناعي.

## الملفات

- `output/khatarat-al-robotat.mp4` — الفيديو النهائي
- `script.txt` — نص التعليق الصوتي
- `audio/narration.mp3` — التعليق بصوت عربي
- `images/` — المشاهد البصرية
- `build_video.py` — سكربت التركيب

## إعادة البناء

```bash
pip install edge-tts pillow arabic-reshaper python-bidi
edge-tts --voice ar-SA-HamedNeural --rate="-5%" --file script.txt --write-media audio/narration.mp3
python3 build_video.py
```
