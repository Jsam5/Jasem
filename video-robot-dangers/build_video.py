#!/usr/bin/env python3
"""Compose a ~1-minute Arabic documentary video about robot dangers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import arabic_reshaper
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"
FRAMES = ROOT / "frames"
AUDIO = ROOT / "audio" / "narration.mp3"
OUTPUT = ROOT / "output" / "khatarat-al-robotat.mp4"
ARTIFACT = Path("/opt/cursor/artifacts/khatarat-al-robotat.mp4")

W, H = 1920, 1080
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"

# Scene plan synced to ~63s narration
SCENES = [
    {
        "src": "00-title-bg.png",
        "duration": 3.5,
        "title": "خطورة الروبوتات",
        "subtitle": "تحدٍ يواجه مستقبل البشرية",
        "darken": 0.55,
    },
    {
        "src": "01-robot-city.png",
        "duration": 8.5,
        "title": "قوة تغيّر المصير",
        "subtitle": "التطور التقني يتسارع... والمخاطر تقترب",
        "darken": 0.7,
    },
    {
        "src": "02-job-loss.png",
        "duration": 8.8,
        "title": "فقدان الوظائف",
        "subtitle": "الآلات تحل محل الإنسان",
        "darken": 0.65,
    },
    {
        "src": "03-loss-of-control.png",
        "duration": 9.2,
        "title": "فقدان السيطرة",
        "subtitle": "أنظمة ذكية قد تخرج عن التحكم",
        "darken": 0.6,
    },
    {
        "src": "04-military.png",
        "duration": 8.5,
        "title": "الاستخدام العسكري",
        "subtitle": "روبوتات قتالية بلا رحمة",
        "darken": 0.65,
    },
    {
        "src": "05-surveillance.png",
        "duration": 8.5,
        "title": "الخصوصية والأمان",
        "subtitle": "بياناتنا تحت المراقبة",
        "darken": 0.65,
    },
    {
        "src": "06-ending.png",
        "duration": 16.0,
        "title": "هل نحن مستعدون؟",
        "subtitle": "الضوابط الأخلاقية هي الطريق",
        "darken": 0.7,
    },
]


def ar(text: str) -> str:
    # Noto + Pillow render reshaped glyphs correctly; python-bidi breaks them here.
    return arabic_reshaper.reshape(text)


def fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def draw_centered(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    # soft shadow
    draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=fill)


def make_frame(scene: dict, index: int) -> Path:
    src = Image.open(IMAGES / scene["src"]).convert("RGB")
    base = fit_cover(src, (W, H))
    base = ImageEnhance.Brightness(base).enhance(scene.get("darken", 0.7))
    base = base.filter(ImageFilter.GaussianBlur(radius=0.4))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # bottom gradient bar
    for i in range(320):
        alpha = int(210 * (i / 320))
        draw.rectangle([(0, H - 320 + i), (W, H - 320 + i + 1)], fill=(0, 8, 16, alpha))

    title_font = ImageFont.truetype(FONT_BOLD, 78 if index == 0 else 64)
    sub_font = ImageFont.truetype(FONT_REG, 36)

    title = ar(scene["title"])
    subtitle = ar(scene["subtitle"])

    if index == 0:
        draw_centered(draw, H // 2 - 70, title, title_font, (230, 245, 255, 255))
        draw_centered(draw, H // 2 + 30, subtitle, sub_font, (160, 200, 220, 255))
    else:
        draw_centered(draw, H - 210, title, title_font, (235, 245, 255, 255))
        draw_centered(draw, H - 120, subtitle, sub_font, (170, 205, 220, 255))

    composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    out = FRAMES / f"scene_{index:02d}.png"
    composed.save(out, "PNG")
    return out


def build() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    frame_paths = [make_frame(scene, i) for i, scene in enumerate(SCENES)]
    total = sum(s["duration"] for s in SCENES)
    print(f"Scenes: {len(SCENES)}, planned duration: {total:.1f}s")

    # Build input list for ffmpeg concat with per-image duration
    list_file = FRAMES / "concat.txt"
    with list_file.open("w", encoding="utf-8") as f:
        for path, scene in zip(frame_paths, SCENES):
            f.write(f"file '{path}'\n")
            f.write(f"duration {scene['duration']}\n")
        # concat demuxer needs last file repeated
        f.write(f"file '{frame_paths[-1]}'\n")

    # Scale/pad + gentle zoom via zoompan on each segment would be heavy;
    # use slideshow with fades between scenes via xfade chain.
    # Simpler reliable path: concat then burn soft crossfades with fps.

    silent_video = FRAMES / "silent.mp4"
    cmd_video = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(silent_video),
    ]
    subprocess.run(cmd_video, check=True)

    # Mux narration; trim/pad video to audio length
    cmd_mux = [
        "ffmpeg",
        "-y",
        "-i",
        str(silent_video),
        "-i",
        str(AUDIO),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(OUTPUT),
    ]
    subprocess.run(cmd_mux, check=True)

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", str(OUTPUT), str(ARTIFACT)], check=True)

    probe = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(OUTPUT),
        ],
        text=True,
    ).strip()
    print(f"Wrote {OUTPUT} ({probe}s)")
    print(f"Copied to {ARTIFACT}")


if __name__ == "__main__":
    build()
