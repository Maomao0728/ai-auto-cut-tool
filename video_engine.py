from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def canvas_size(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio.startswith("9:16"):
        return 720, 1280
    if aspect_ratio.startswith("1:1"):
        return 1080, 1080
    return 1280, 720


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
        path = Path(font_path)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def resize_cover(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    src_h, src_w = frame.shape[:2]
    scale = max(width / src_w, height / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    x1 = max((new_w - width) // 2, 0)
    y1 = max((new_h - height) // 2, 0)
    return resized[y1 : y1 + height, x1 : x1 + width]


def wrap_text(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(text, width=max_chars) or [text]


def draw_overlay(frame: np.ndarray, subtitle: str, style: str, keywords: list[str]) -> np.ndarray:
    height, width = frame.shape[:2]
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    title_font = load_font(max(28, width // 34))
    tag_font = load_font(max(18, width // 58))
    subtitle_font = load_font(max(30, width // 32))

    draw.rectangle([(0, 0), (width, int(height * 0.18))], fill=(0, 0, 0, 96))
    draw.text((40, 28), "AI 全自动剪辑 · " + style, font=title_font, fill=(255, 255, 255, 245))

    x = 40
    y = 80
    for keyword in keywords[:4]:
        tag = f"#{keyword}"
        box = draw.textbbox((0, 0), tag, font=tag_font)
        tag_w = box[2] - box[0] + 28
        draw.rounded_rectangle([(x, y), (x + tag_w, y + 34)], radius=17, fill=(22, 119, 255, 210))
        draw.text((x + 14, y + 5), tag, font=tag_font, fill=(255, 255, 255, 245))
        x += tag_w + 10

    bottom_h = int(height * 0.24)
    draw.rectangle([(0, height - bottom_h), (width, height)], fill=(0, 0, 0, 136))
    max_chars = 22 if width < height else 34
    lines = wrap_text(subtitle, max_chars=max_chars)[:3]
    line_height = 46
    total_h = len(lines) * line_height
    start_y = height - bottom_h + max((bottom_h - total_h) // 2, 8)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=subtitle_font)
        text_w = bbox[2] - bbox[0]
        draw.text(((width - text_w) // 2, start_y), line, font=subtitle_font, fill=(255, 255, 255, 255))
        start_y += line_height

    composed = Image.alpha_composite(image, overlay).convert("RGB")
    return cv2.cvtColor(np.array(composed), cv2.COLOR_RGB2BGR)


def make_gradient_frame(width: int, height: int, index: int) -> np.ndarray:
    x = np.linspace(0, 1, width, dtype=np.float32)
    y = np.linspace(0, 1, height, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)
    base = np.zeros((height, width, 3), dtype=np.uint8)
    base[:, :, 0] = np.clip(40 + 70 * xv + index * 8, 0, 255)
    base[:, :, 1] = np.clip(80 + 80 * yv, 0, 255)
    base[:, :, 2] = np.clip(170 + 55 * (1 - xv), 0, 255)
    return base


def _normalize_filename(value: str) -> str:
    return value.lower().replace(" ", "").replace("_", "").replace("-", "")


def _preferred_material_name(segment_index: int, storyboard: list[dict[str, Any]]) -> str:
    if 0 <= segment_index < len(storyboard):
        return str(storyboard[segment_index].get("匹配素材", ""))
    return ""


def _camera_motion(item: dict[str, Any], segment_index: int) -> str:
    motion = str(item.get("运镜方式", "自动运镜")).strip()
    if not motion or motion == "自动运镜":
        return ["缓慢推近", "从右到左", "从上到下", "从左到右"][segment_index % 4]
    return motion


def _pick_image(image_paths: list[Path], segment_index: int, storyboard: list[dict[str, Any]]) -> Path:
    preferred_name = _preferred_material_name(segment_index, storyboard)
    if preferred_name:
        normalized_preferred = _normalize_filename(preferred_name)
        for candidate in image_paths:
            if _normalize_filename(candidate.name) == normalized_preferred:
                return candidate
    return image_paths[segment_index % len(image_paths)]

def animated_image_frame(
    image_paths: list[Path],
    width: int,
    height: int,
    segment_index: int,
    frame_index: int,
    frames_in_segment: int,
    storyboard: list[dict[str, Any]],
) -> np.ndarray | None:
    if not image_paths:
        return None
    raw = cv2.imdecode(np.fromfile(str(_pick_image(image_paths, segment_index, storyboard)), dtype=np.uint8), cv2.IMREAD_COLOR)
    if raw is None:
        return None

    progress = frame_index / max(frames_in_segment - 1, 1)
    motion = _camera_motion(storyboard[segment_index], segment_index) if 0 <= segment_index < len(storyboard) else "缓慢推近"
    base_scale = max(width / raw.shape[1], height / raw.shape[0])
    if "拉远" in motion:
        zoom = 1.12 - 0.12 * progress
    elif "固定" in motion or "无" in motion:
        zoom = 1.0
    else:
        zoom = 1.0 + 0.12 * progress

    scale = base_scale * zoom
    new_w = max(width, int(raw.shape[1] * scale))
    new_h = max(height, int(raw.shape[0] * scale))
    resized = cv2.resize(raw, (new_w, new_h), interpolation=cv2.INTER_AREA)
    max_x = max(new_w - width, 0)
    max_y = max(new_h - height, 0)

    if "固定" in motion or "无" in motion:
        x = int(max_x * 0.5)
        y = int(max_y * 0.5)
    elif "左到右" in motion:
        x = int(max_x * progress)
        y = int(max_y * 0.5)
    elif "右到左" in motion:
        x = int(max_x * (1 - progress))
        y = int(max_y * 0.5)
    elif "上到下" in motion:
        x = int(max_x * 0.5)
        y = int(max_y * progress)
    elif "下到上" in motion:
        x = int(max_x * 0.5)
        y = int(max_y * (1 - progress))
    else:
        direction = segment_index % 4
        if direction == 0:
            x = int(max_x * progress)
            y = int(max_y * 0.35)
        elif direction == 1:
            x = int(max_x * (1 - progress))
            y = int(max_y * 0.65)
        elif direction == 2:
            x = int(max_x * 0.5)
            y = int(max_y * progress)
        else:
            x = int(max_x * 0.5)
            y = int(max_y * (1 - progress))

    frame = resized[y : y + height, x : x + width]
    if frame.shape[0] != height or frame.shape[1] != width:
        frame = resize_cover(raw, width, height)
    return frame


def video_frame_reader(video_paths: list[Path], width: int, height: int):
    if not video_paths:
        while True:
            yield None
    video_index = 0
    cap = cv2.VideoCapture(str(video_paths[video_index]))
    while True:
        ok, frame = cap.read()
        if not ok:
            cap.release()
            video_index = (video_index + 1) % len(video_paths)
            cap = cv2.VideoCapture(str(video_paths[video_index]))
            ok, frame = cap.read()
            if not ok:
                yield None
                continue
        yield resize_cover(frame, width, height)


def _read_video_frame(video_path: Path, width: int, height: int, frame_offset: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    if frame_offset > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_offset)
    ok, frame = cap.read()
    if not ok:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None
    return resize_cover(frame, width, height)


def _pick_video_frame(
    video_paths: list[Path],
    width: int,
    height: int,
    segment_index: int,
    frame_index: int,
    storyboard: list[dict[str, Any]],
    fallback_reader: Any,
) -> np.ndarray | None:
    preferred_name = _preferred_material_name(segment_index, storyboard)
    if preferred_name:
        normalized_preferred = _normalize_filename(preferred_name)
        for candidate in video_paths:
            if _normalize_filename(candidate.name) == normalized_preferred:
                return _read_video_frame(candidate, width, height, frame_index)
    return next(fallback_reader)


def mux_audio(
    video_path: Path,
    voice_path: Path | None,
    music_path: Path | None,
    output_path: Path,
    duration: int,
) -> bool:
    if not voice_path and not music_path:
        return False

    command = ["ffmpeg", "-y", "-i", str(video_path)]
    if voice_path:
        command += ["-i", str(voice_path)]
    if music_path:
        command += ["-stream_loop", "-1", "-i", str(music_path)]

    if voice_path and music_path:
        command += [
            "-t", str(duration),
            "-filter_complex", "[1:a]volume=1.0[a1];[2:a]volume=0.18[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v:0", "-map", "[aout]",
        ]
    elif voice_path:
        command += ["-map", "0:v:0", "-map", "1:a:0"]
    else:
        command += ["-t", str(duration), "-filter:a", "volume=0.22", "-map", "0:v:0", "-map", "1:a:0"]

    command += ["-c:v", "copy", "-c:a", "aac", "-shortest", str(output_path)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return result.returncode == 0 and output_path.exists()


def compose_basic_video(
    video_paths: list[Path],
    image_paths: list[Path],
    music_path: Path | None,
    voice_path: Path | None,
    storyboard: list[dict[str, Any]],
    style: str,
    aspect_ratio: str,
    target_duration: int,
    run_dir: Path,
) -> Path:
    width, height = canvas_size(aspect_ratio)
    fps = 24
    silent_output = run_dir / "basic_video_without_bgm.mp4"
    final_output = run_dir / "ai_auto_cut_demo.mp4"

    writer = cv2.VideoWriter(str(silent_output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("视频写入器启动失败，请确认 OpenCV/FFmpeg 安装正常。")

    reader = video_frame_reader(video_paths, width, height)
    written = 0
    for index, item in enumerate(storyboard):
        seconds = float(str(item["建议时长"]).replace("秒", ""))
        frames_needed = max(1, int(math.ceil(seconds * fps)))
        for frame_index in range(frames_needed):
            frame = _pick_video_frame(video_paths, width, height, index, frame_index, storyboard, reader)
            if frame is None:
                frame = animated_image_frame(image_paths, width, height, index, frame_index, frames_needed, storyboard)
            if frame is None:
                frame = make_gradient_frame(width, height, index)
            frame = draw_overlay(frame, str(item["文案"]), style, list(item["画面关键词"]))
            writer.write(frame)
            written += 1
    writer.release()

    if written == 0 or not silent_output.exists():
        raise RuntimeError("没有生成有效视频帧，请检查素材格式。")
    if voice_path or music_path:
        if mux_audio(silent_output, voice_path, music_path, final_output, target_duration):
            return final_output
    return silent_output
