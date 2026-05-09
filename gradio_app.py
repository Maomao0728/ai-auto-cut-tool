from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr

from api_config import get_app_config
from matching_engine import assign_materials_to_storyboard
from llm_engine import generate_storyboard
from video_engine import compose_basic_video
from tts_engine import estimate_voice_duration, get_audio_duration, synthesize_tts
from vision_engine import analyze_material_tags

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
ASSETS_DIR = PROJECT_ROOT / "assets"
LIBRARY_DIR = ASSETS_DIR / "library"
MUSIC_DIR = ASSETS_DIR / "music"
TEMP_DIR = PROJECT_ROOT / "temp"

for folder in (INPUT_DIR, OUTPUT_DIR, ASSETS_DIR, MUSIC_DIR, LIBRARY_DIR, TEMP_DIR):
    folder.mkdir(parents=True, exist_ok=True)

DEMO_MUSIC = {
    "企业宣传｜稳重科技感": "corporate_tech.mp3",
    "产品介绍｜轻快明亮": "product_bright.mp3",
    "汇报展示｜大气正式": "report_grand.mp3",
    "业务宣传｜温暖可信": "warm_service.mp3",
    "暂不添加音乐": "none",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

STYLE_PRESETS = {
    "政务/民生宣传": ["政务大厅", "办事窗口", "工作人员", "群众", "服务", "数据大屏", "城市", "政策"],
    "产品介绍": ["产品界面", "功能演示", "用户操作", "数据看板", "效率提升", "解决方案"],
    "业务介绍": ["团队协作", "客户沟通", "业务流程", "办公场景", "数字化", "成果展示"],
    "汇报总结": ["会议", "数据图表", "项目成果", "团队", "里程碑", "未来规划"],
}

CSS = """
:root {
  --bg: #080b12;
  --panel: rgba(17, 24, 39, 0.86);
  --line: rgba(148, 163, 184, 0.18);
  --brand: #28d7e8;
  --brand-2: #6d5dfc;
}
.gradio-container {
  max-width: none !important;
  width: 100vw !important;
  margin: 0 auto !important;
  min-height: 100vh !important;
  overflow-x: hidden !important;
  background: radial-gradient(circle at 72% 8%, rgba(40, 215, 232, 0.20), transparent 30%), linear-gradient(135deg, #080b12 0%, #101827 42%, #eef4ff 42%, #f8fafc 100%);
}
.app-shell { padding: 0 28px 18px; width: 100%; box-sizing: border-box; }
.topbar { display: none; }
.logo { font-size: 26px; font-weight: 900; letter-spacing: -0.03em; text-align: center; }
.logo span { color: var(--brand); }
.page-title { text-align:center; color:#e5faff; font-size:30px; font-weight:900; letter-spacing:-0.04em; margin: 0 0 14px; }
.page-title span { color: var(--brand); }
.lang-pill { display: none; }
.layout-row { align-items: stretch !important; min-height: calc(100vh - 20px); width: 100% !important; gap: 26px !important; }
.sidebar {
  min-height: calc(100vh - 24px);
  border-radius: 24px;
  padding: 18px 12px 16px;
  background: rgba(5, 8, 15, 0.84);
  border: 1px solid rgba(255,255,255,.08);
  box-shadow: 0 24px 80px rgba(0,0,0,.28);
}
.nav-title { display: none; }
.nav-item { display: flex; align-items: center; gap: 10px; color: #cbd5e1; padding: 12px; border-radius: 14px; margin: 4px 0; font-size: 14px; }
.nav-button button {
  width: 100% !important; justify-content: flex-start !important; border-radius: 14px !important;
  border: 1px solid rgba(255,255,255,.08) !important; background: transparent !important;
  color: #cbd5e1 !important; box-shadow: none !important; padding: 10px 12px !important; font-size: 14px !important;
}
.nav-button.active button { background: rgba(40, 215, 232, .14) !important; color: #ffffff !important; border-color: rgba(40,215,232,.28) !important; }
.nav-button button:hover { background: rgba(255,255,255,.08) !important; color: #fff !important; }
.nav-item.active { background: rgba(40, 215, 232, .14); color: white; border: 1px solid rgba(40,215,232,.28); }
.nav-item.dim { opacity: .62; }
.file-btn { max-width: 118px !important; min-width: 100px !important; }
.file-btn button, .file-btn .wrap {
  min-height: 40px !important; border-radius: 999px !important; background: rgba(15,23,42,.92) !important;
  color: #fff !important; border: 1px solid rgba(255,255,255,.16) !important;
}
.file-btn label { font-size: 12px !important; }
.action-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.hero-card {
  width: 100%;
  border-radius: 28px;
  min-height: 170px;
  padding: 24px 48px 30px;
  background: linear-gradient(105deg, rgba(11, 95, 111, .95), rgba(15, 23, 42, .78)), url('https://images.unsplash.com/photo-1639322537228-f710d846310a?auto=format&fit=crop&w=1600&q=80');
  background-size: cover; background-position: center;
  color: white; box-shadow: 0 18px 70px rgba(2, 6, 23, .22);
}
.hero-card h1 { font-size: 34px; margin: 0 0 8px; letter-spacing: -0.04em; line-height: 1.05; }
.hero-card p { margin: 0 0 12px; color: #ffffff; }
.hero-card p strong { color: #ffffff !important; font-weight: 800; }
.section-card, .result-card, .center-generate { background: rgba(255,255,255,.94); border: 1px solid rgba(148,163,184,.18); border-radius: 24px; padding: 20px; box-shadow: 0 18px 60px rgba(15,23,42,.08); width: 100%; box-sizing: border-box; }
.home-stage { min-height: 240px; display: flex; align-items: stretch; width: 100%; }
.center-generate { min-height: 240px; display: flex; align-items: center; justify-content: center; width: 100%; }
.center-generate button {
  max-width: 260px !important;
  height: 54px !important;
  font-size: 18px !important;
  border-radius: 999px !important;
  cursor: pointer !important;
  transition: transform .18s ease, box-shadow .18s ease, filter .18s ease, background .18s ease !important;
}
.center-generate button:hover {
  transform: translateY(-3px) scale(1.04) !important;
  filter: brightness(1.14) saturate(1.18) !important;
  box-shadow: 0 18px 38px rgba(34, 211, 238, .34), 0 10px 26px rgba(124, 58, 237, .28) !important;
  background: linear-gradient(135deg, #38e8ff, #8b5cf6) !important;
}
.center-generate button:active {
  transform: translateY(-1px) scale(.99) !important;
}
.result-card { position: sticky; top: 18px; }
.step-title { font-weight: 800; font-size: 18px; color: #0f172a; margin: 0 0 4px; }
.step-desc { color: #64748b; font-size: 13px; margin-bottom: 12px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 0; }
.chip { padding: 8px 12px; border-radius: 999px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.18); font-size: 12px; }
.download-row { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 12px 0; }
.metric { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 12px; }
.metric strong { display: block; font-size: 19px; color: #0f766e; }
.metric span { color: #64748b; font-size: 12px; }
button.primary, .primary button { background: linear-gradient(135deg, #22d3ee, #7c3aed) !important; border: none !important; color: white !important; }
.module-title { margin: 0 0 6px !important; padding: 0 !important; font-size: 34px !important; line-height: 1.05 !important; font-weight: 900 !important; letter-spacing: -0.04em !important; color: #07111f !important; }
.module-subtitle { margin: 0 0 16px !important; padding: 0 !important; font-size: 15px !important; color: #334155 !important; }
.footer-note { color: #94a3b8; text-align:center; font-size: 12px; padding: 18px 0 0; }
.wide-page { width: 100% !important; }
.wide-row { width: 100% !important; align-items: stretch !important; gap: 22px !important; }
.workspace-tabs, .workspace-tabs > div, .workspace-tabs .tabitem { width: 100% !important; }
.result-downloads { display: flex; gap: 12px; justify-content: flex-end; align-items: center; }

.block, .form, .panel { border-radius: 18px !important; }
@media (max-width: 1000px) {
  .sidebar { min-height: auto; }
  .hero-card h1 { font-size: 28px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.sidebar .gr-button,
.sidebar button,
.sidebar button.secondary,
.sidebar .nav-button button {
  width: 100% !important;
  min-height: 48px !important;
  margin: 0 0 16px 0 !important;
  border-radius: 16px !important;
  border: 1px solid rgba(34, 211, 238, 0.22) !important;
  background: rgba(15, 23, 42, 0.76) !important;
  color: #e5faff !important;
  font-size: 15px !important;
  font-weight: 800 !important;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22) !important;
  transition: transform .18s ease, box-shadow .18s ease, background .18s ease, border-color .18s ease !important;
}
.sidebar .gr-button:hover,
.sidebar button:hover,
.sidebar .nav-button button:hover {
  background: rgba(34, 211, 238, 0.16) !important;
  border-color: rgba(34, 211, 238, 0.5) !important;
  color: #ffffff !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 18px 36px rgba(34, 211, 238, 0.28), 0 10px 24px rgba(124, 58, 237, 0.24) !important;
}
.sidebar .nav-button.active button {
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.28), rgba(124, 58, 237, 0.26)) !important;
  color: #ffffff !important;
  border-color: rgba(34, 211, 238, 0.55) !important;
}
.sidebar-generate button {
  background: linear-gradient(135deg, #22d3ee, #7c3aed) !important;
  border: none !important;
  color: #ffffff !important;
  font-size: 17px !important;
  font-weight: 900 !important;
  letter-spacing: .02em !important;
}.module-title {
  margin: 0 0 6px !important;
  padding: 0 !important;
  font-size: 34px !important;
  line-height: 1.05 !important;
  font-weight: 900 !important;
  letter-spacing: -0.04em !important;
  color: #07111f !important;
}
.module-subtitle {
  margin: 0 0 16px !important;
  padding: 0 !important;
  font-size: 15px !important;
  color: #334155 !important;
}.workspace-tabs > div:first-child {
  display: none !important;
}
.workspace-tabs .tabitem {
  padding-top: 0 !important;
}html, body, gradio-app {
  width: 100% !important;
  min-width: 1280px !important;
  margin: 0 !important;
  background: #05070d !important;
}
.gradio-container,
.gradio-container .main,
.gradio-container main,
.gradio-container .contain,
.gradio-container .wrap {
  max-width: none !important;
  width: 100% !important;
  min-width: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  box-sizing: border-box !important;
}
.app-shell {
  min-height: 100vh !important;
  padding: 24px 32px !important;
  background: radial-gradient(circle at 70% 0%, rgba(40,215,232,.18), transparent 28%), linear-gradient(135deg, #05070d 0%, #0d1320 24%, #111827 52%, #edf7ff 52%, #f8fafc 100%) !important;
}
.layout-row {
  display: flex !important;
  width: 100% !important;
  max-width: none !important;
  gap: 32px !important;
  flex-wrap: nowrap !important;
}
.layout-row > .gradio-column:first-child {
  flex: 0 0 240px !important;
  max-width: 240px !important;
  min-width: 240px !important;
}
.layout-row > .gradio-column:last-child {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  max-width: none !important;
}
.sidebar {
  min-height: calc(100vh - 48px) !important;
  border-radius: 28px !important;
  padding: 28px 18px !important;
}
.workspace-tabs,
.workspace-tabs > div,
.workspace-tabs .tabitem,
.workspace-tabs [role="tabpanel"] {
  width: 100% !important;
  max-width: none !important;
}
.wide-row {
  display: flex !important;
  flex-wrap: nowrap !important;
  width: 100% !important;
  gap: 24px !important;
}
.wide-row > .gradio-column {
  min-width: 0 !important;
}
.page-title {
  text-align: left !important;
  font-size: 34px !important;
  margin-left: 4px !important;
}
.hero-card {
  min-height: 250px !important;
  padding: 52px 64px !important;
  border-radius: 28px !important;
}
.hero-card h1 {
  font-size: 44px !important;
}
.center-generate {
  min-height: 260px !important;
}
.center-generate button {
  max-width: 320px !important;
  width: 260px !important;
  height: 64px !important;
  font-size: 20px !important;
}
.section-card, .result-card {
  min-height: 100% !important;
}
textarea, .input-container textarea {
  min-height: 360px !important;
}body, gradio-app, .gradio-container {
  min-height: 100vh !important;
  overflow-y: auto !important;
}
.gradio-container {
  padding: 24px 32px !important;
  background: radial-gradient(circle at 74% 0%, rgba(40,215,232,.16), transparent 28%), linear-gradient(135deg, #05070d 0%, #0d1320 26%, #111827 46%, #eaf7ff 46%, #f8fafc 100%) !important;
}
.layout-row {
  min-height: calc(100vh - 48px) !important;
  margin: 0 !important;
}
.workspace-tabs {
  padding-top: 0 !important;
}
.module-title,
.page-title {
  color: #f8fdff !important;
  text-shadow: 0 2px 16px rgba(0, 0, 0, .45) !important;
}
.module-subtitle {
  color: rgba(248, 253, 255, .9) !important;
  text-shadow: 0 1px 10px rgba(0, 0, 0, .35) !important;
}
.section-card .module-subtitle,
.result-card .module-subtitle,
.hero-card .module-subtitle {
  color: #334155 !important;
  text-shadow: none !important;
}
.workspace-tabs > div:first-child {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
}
footer, .footer-note {
  display: none !important;
}"""

def _safe_name(path: str | Path) -> str:
    return Path(path).name.replace(" ", "_")


def _save_uploads(files: list[Any] | None, target_dir: Path) -> list[Path]:
    saved: list[Path] = []
    if not files:
        return saved
    target_dir.mkdir(parents=True, exist_ok=True)
    for file_obj in files:
        src = Path(file_obj.name if hasattr(file_obj, "name") else str(file_obj))
        if not src.exists():
            continue
        dst = target_dir / _safe_name(src)
        shutil.copy2(src, dst)
        saved.append(dst)
    return saved


def _library_choices() -> list[str]:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    files = [path for path in LIBRARY_DIR.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS]
    return [path.name for path in sorted(files, key=lambda item: item.name.lower())]


def _copy_library_items(names: list[str] | None, target_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    saved_videos: list[Path] = []
    saved_images: list[Path] = []
    saved_audio: list[Path] = []
    if not names:
        return saved_videos, saved_images, saved_audio
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = LIBRARY_DIR / Path(name).name
        if not src.exists() or not src.is_file():
            continue
        dst = target_dir / _safe_name(src)
        shutil.copy2(src, dst)
        if dst.suffix.lower() in VIDEO_EXTENSIONS:
            saved_videos.append(dst)
        elif dst.suffix.lower() in IMAGE_EXTENSIONS:
            saved_images.append(dst)
        elif dst.suffix.lower() in AUDIO_EXTENSIONS:
            saved_audio.append(dst)
    return saved_videos, saved_images, saved_audio

def save_to_material_library(files: list[Any] | None) -> tuple[gr.CheckboxGroup, str]:
    saved = _save_uploads(files, LIBRARY_DIR)
    choices = _library_choices()
    if not saved:
        return gr.CheckboxGroup(choices=choices, value=[]), "没有选择可保存的素材。"
    return gr.CheckboxGroup(choices=choices, value=[path.name for path in saved]), f"已加入素材库：{len(saved)} 个文件。"


def _resolve_music_path(music_choice: str, custom_music_path: Path | None) -> tuple[Path | None, str, str]:
    if custom_music_path:
        return custom_music_path, custom_music_path.name, "custom"
    music_filename = DEMO_MUSIC.get(music_choice, "none")
    if music_filename == "none":
        return None, "暂不添加音乐", "none"
    library_music_path = MUSIC_DIR / music_filename
    if library_music_path.exists():
        return library_music_path, music_choice, "library"
    return None, f"{music_choice}（未找到 {music_filename}）", "missing"


def delete_from_material_library(names: list[str] | None) -> tuple[gr.CheckboxGroup, str]:
    choices_before = _library_choices()
    if not names:
        return gr.CheckboxGroup(choices=choices_before, value=[]), "请先勾选要删除的素材。"

    deleted = 0
    failed: list[str] = []
    for name in names:
        safe_name = Path(name).name
        target = LIBRARY_DIR / safe_name
        try:
            if target.exists() and target.is_file() and target.parent.resolve() == LIBRARY_DIR.resolve():
                target.unlink()
                deleted += 1
            else:
                failed.append(safe_name)
        except Exception:
            failed.append(safe_name)

    choices_after = _library_choices()
    message = f"已删除素材：{deleted} 个。"
    if failed:
        message += f" 删除失败/未找到：{', '.join(failed)}。"
    return gr.CheckboxGroup(choices=choices_after, value=[]), message


def refresh_material_library() -> gr.CheckboxGroup:
    return gr.CheckboxGroup(choices=_library_choices(), value=[])


def _time_to_seconds(value: str) -> float:
    parts = [int(part) for part in value.strip().split(":")]
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    return 0.0


def _extract_quoted_text(text: str) -> str:
    matches = re.findall(r"[“\"]([^”\"]{8,})[”\"]", text, flags=re.S)
    if matches:
        return "".join(item.strip() for item in matches)
    return ""


def _extract_field(block: str, field_names: list[str]) -> str:
    starts = []
    for field in field_names:
        match = re.search(rf"{re.escape(field)}\s*[:：]", block)
        if match:
            starts.append((match.start(), match.end()))
    if not starts:
        return ""
    _, content_start = min(starts, key=lambda item: item[0])
    next_matches = list(re.finditer(r"(?:画面|分镜素材指示|人物状态|特效|口播文案|台词|BGM|音乐|时间轴)\s*[:：]", block[content_start:]))
    end = content_start + next_matches[0].start() if next_matches else len(block)
    return block[content_start:end].strip(" \n\t。")


def _strip_suggestion_columns(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.replace("｜", "|").strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2 and re.fullmatch(r"\d+(?:\.\d+)?秒?", parts[1].replace(" ", "")):
            lines.append(parts[0])
            continue
        if len(parts) >= 3 and re.fullmatch(r"\d+(?:\.\d+)?", parts[1].replace(" ", "")) and any(parts[2:]):
            lines.append(parts[0])
            continue
        lines.append(raw_line)
    cleaned = "\n".join(lines).strip()
    return cleaned or text.strip()


def _parse_timeline_script(script: str) -> tuple[list[dict[str, Any]], str]:
    pattern = re.compile(r"(?P<start>\d{1,2}:\d{2})(?:\s*[-—~至]\s*)(?P<end>\d{1,2}:\d{2})")
    matches = list(pattern.finditer(script))
    if not matches:
        return [], script

    storyboard: list[dict[str, Any]] = []
    voice_parts: list[str] = []
    for index, match in enumerate(matches):
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(script)
        block = script[block_start:block_end].strip()
        start = _time_to_seconds(match.group("start"))
        end = _time_to_seconds(match.group("end"))
        duration = max(2.0, round(end - start, 1))
        voice_text = _extract_field(block, ["口播文案", "台词", "配音文案"])
        if not voice_text:
            voice_text = _extract_quoted_text(block)
        if not voice_text:
            voice_text = _strip_suggestion_columns(block)
        visual_prompt = _extract_field(block, ["画面", "分镜素材指示", "画面 / 分镜素材指示"])
        character_effects = _extract_field(block, ["人物状态", "特效", "人物状态 / 特效"])
        combined_for_keywords = " ".join([visual_prompt, character_effects, voice_text])
        keywords = _mock_match(combined_for_keywords, "业务介绍")
        if "cyber" in combined_for_keywords.lower() or "hacker" in combined_for_keywords.lower():
            keywords = ["科技", "黑客", "数据", "警告"]
        storyboard.append(
            {
                "序号": index + 1,
                "时间轴": f"{match.group('start')}-{match.group('end')}",
                "文案": voice_text,
                "画面提示": visual_prompt or block[:180],
                "人物状态/特效": character_effects,
                "建议时长": f"{duration}秒",
                "画面关键词": keywords,
                "运镜方式": "自动运镜",
                "镜头建议": visual_prompt or "按脚本画面提示匹配素材。",
            }
        )
        voice_parts.append(voice_text)
    return storyboard, "".join(voice_parts)


def _parse_custom_storyboard(custom_storyboard: str) -> list[dict[str, Any]]:
    rows = [row.strip() for row in custom_storyboard.splitlines() if row.strip()]
    storyboard: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        parts = [part.strip() for part in row.replace("｜", "|").split("|")]
        if len(parts) < 2:
            continue
        text = _strip_suggestion_columns(parts[0])
        duration_text = parts[1]
        camera = "自动运镜"
        keywords = [item.strip() for item in re.split(r"[、,，/]", parts[2])] if len(parts) > 2 and parts[2] else _mock_match(text, "业务介绍")
        material_hint = parts[3] if len(parts) > 3 else ""
        visual_prompt = parts[4] if len(parts) > 4 else ""
        try:
            duration = max(1.0, float(duration_text.replace("秒", "").strip()))
        except ValueError:
            duration = 3.0
        storyboard.append(
            {
                "序号": index,
                "文案": text,
                "建议时长": f"{duration}秒",
                "画面关键词": keywords[:6],
                "运镜方式": camera,
                "自定义素材": material_hint,
                "画面提示": visual_prompt,
                "镜头建议": visual_prompt or f"按自定义分镜匹配：{' / '.join(keywords[:6])}",
            }
        )
    return storyboard


def _mock_match(sentence: str, style: str) -> list[str]:
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["业务介绍"])
    lower_sentence = sentence.lower()
    matched: list[str] = []
    priority_terms = ["峰会", "展会", "入口", "注册", "导览", "展台", "政务", "助手", "智慧", "服务", "平台", "城市", "治理", "民生", "科技", "创新", "支付", "生活", "群众", "办事", "体验", "互动", "团队", "产品", "展示", "未来", "全景", "合影", "讲解", "签到", "路演"]
    for term in priority_terms:
        if term in sentence and term not in matched:
            matched.append(term)
    for keyword in preset:
        if (keyword[:2] in sentence or keyword in sentence) and keyword not in matched:
            matched.append(keyword)
    if not matched:
        for keyword in preset:
            if any(token in lower_sentence for token in ["服务", "产品", "数据", "业务", "群众", "就业", "政务", "汇报", "ai", "智能"]):
                if keyword not in matched:
                    matched.append(keyword)
            if len(matched) >= 4:
                break
    return matched[:4] or preset[:4]


def build_demo_plan(
    materials: list[Any] | None,
    images: list[Any] | None,
    script: str,
    music_choice: str,
    custom_music: Any,
    style: str,
    target_duration: int,
    voice_style: str,
    aspect_ratio: str,
    custom_storyboard: str,
    library_items: list[str] | None,
) -> tuple[str, str | None, str, str | None, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"demo_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    saved_videos = _save_uploads(materials, run_dir / "materials")
    saved_images = _save_uploads(images, run_dir / "images")
    library_videos, library_images, library_audio = _copy_library_items(library_items, run_dir / "library_materials")
    saved_videos.extend(library_videos)
    saved_images.extend(library_images)
    custom_music_path = library_audio[0] if library_audio else None
    if custom_music is not None:
        music_files = _save_uploads([custom_music], run_dir / "music")
        custom_music_path = music_files[0] if music_files else None

    if not script.strip() and not (custom_storyboard or "").strip():
        return "请先到「文案与分镜」页面输入宣传文案，或填写自定义分镜后再生成。", None, "", None, gr.update(selected="result")

    custom_storyboard_items = _parse_custom_storyboard(custom_storyboard or "")
    cleaned_script = _strip_suggestion_columns(script)
    timeline_storyboard, voice_script = ([], "")
    storyboard_message = ""

    if custom_storyboard_items:
        storyboard = custom_storyboard_items
        storyboard_message = "用户自定义分镜"
    else:
        timeline_storyboard, voice_script = _parse_timeline_script(cleaned_script)
        if timeline_storyboard:
            storyboard = timeline_storyboard
        else:
            # 先按目标时长生成分镜，再用分镜文案合成配音，保证字音严格对齐
            storyboard, storyboard_message = generate_storyboard(cleaned_script, style, target_duration)

    storyboard_tts_script = "\n".join(str(item.get("文案", "")).strip() for item in storyboard if str(item.get("文案", "")).strip())
    if not storyboard_tts_script:
        storyboard_tts_script = voice_script if voice_script else cleaned_script

    voice_path, _ = synthesize_tts(storyboard_tts_script, run_dir, voice_style)
    real_voice_duration = get_audio_duration(voice_path)

    # 硬同步：按配音总时长将每句分镜时长重分配，确保字幕切换与口播段落一致
    if storyboard:
        sync_total = real_voice_duration if real_voice_duration > 0 else estimate_voice_duration(storyboard_tts_script, 0)
        sentence_lengths = [max(1, len(str(item.get("文案", "")).strip())) for item in storyboard]
        total_len = sum(sentence_lengths) or 1
        raw_durations = [max(0.6, sync_total * (length / total_len)) for length in sentence_lengths]
        rounded = [round(value, 2) for value in raw_durations]
        delta = round(sync_total - sum(rounded), 2)
        if rounded:
            rounded[-1] = max(0.6, round(rounded[-1] + delta, 2))
        for idx, item in enumerate(storyboard):
            item["建议时长"] = f"{rounded[idx]}秒"

    effective_duration = max(target_duration, int(real_voice_duration + 1.5), int(estimate_voice_duration(storyboard_tts_script, 0)))
    effective_duration = max(effective_duration, int(sum(float(str(item["建议时长"]).replace("秒", "")) for item in storyboard)))
    all_materials = saved_images + saved_videos
    material_tags, vision_message = analyze_material_tags(all_materials)
    storyboard = assign_materials_to_storyboard(storyboard, all_materials, material_tags)

    selected_music_path, selected_music, _ = _resolve_music_path(music_choice, custom_music_path)
    summary = {
        "项目类型": style,
        "目标时长": f"{effective_duration}秒",
        "画面比例": aspect_ratio,
        "配音风格": voice_style,
        "音乐选择": selected_music,
        "上传视频数量": len(saved_videos),
        "上传图片数量": len(saved_images),
        "素材库调用数量": len(library_items or []),
        "素材标签分析": vision_message,
        "脚本模式": "自定义分镜" if custom_storyboard_items else ("详细时间轴脚本" if timeline_storyboard else "LLM/本地增强分镜"),
        "分镜生成说明": storyboard_message or "用户自定义/时间轴脚本",
        "分镜数量": len(storyboard),
    }

    debug_payload = {
        "summary": summary,
        "storyboard_texts": [
            {
                "序号": item.get("序号"),
                "文案": item.get("文案", ""),
                "建议时长": item.get("建议时长", ""),
                "画面关键词": item.get("画面关键词", []),
                "匹配素材": item.get("匹配素材", ""),
                "匹配原因": item.get("匹配原因", ""),
            }
            for item in storyboard
        ],
        "tts_script": storyboard_tts_script,
    }
    plan_path = run_dir / "storyboard_plan.json"
    plan_path.write_text(json.dumps({"summary": summary, "storyboard": storyboard}, ensure_ascii=False, indent=2), encoding="utf-8")
    debug_path = run_dir / "debug_storyboard.json"
    debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    video_path = None
    try:
        video_path = compose_basic_video(
            video_paths=saved_videos,
            image_paths=saved_images,
            music_path=selected_music_path,
            voice_path=voice_path,
            storyboard=storyboard,
            style=style,
            aspect_ratio=aspect_ratio,
            target_duration=effective_duration,
            run_dir=run_dir,
        )
    except Exception:
        video_path = None

    markdown = "## 分镜与素材匹配\n\n"
    if custom_storyboard_items:
        markdown += "| 句子 | 建议时长 | 画面关键词 | 自定义素材 | 匹配素材 | 匹配说明 |\n|---|---:|---|---|---|---|\n"
        for item in storyboard:
            markdown += f"| {item['文案']} | {item['建议时长']} | {'、'.join(item['画面关键词'])} | {item.get('自定义素材', '')} | {item.get('匹配素材', '模板背景')} | {item.get('匹配原因', '按自定义分镜匹配')} |\n"
    elif timeline_storyboard:
        markdown += "| 时间轴 | 口播文案 | 建议时长 | 画面提示 | 人物/特效 | 匹配素材 |\n|---|---|---:|---|---|---|\n"
        for item in storyboard:
            visual = str(item.get("画面提示", ""))[:90].replace("|", "/")
            effect = str(item.get("人物状态/特效", ""))[:60].replace("|", "/")
            markdown += f"| {item.get('时间轴', '')} | {item['文案']} | {item['建议时长']} | {visual} | {effect} | {item.get('匹配素材', '模板背景')} |\n"
    else:
        markdown += "| 句子 | 建议时长 | 画面关键词 | 匹配素材 | 匹配说明 |\n|---|---:|---|---|---|\n"
        for item in storyboard:
            markdown += f"| {item['文案']} | {item['建议时长']} | {'、'.join(item['画面关键词'])} | {item.get('匹配素材', '模板背景')} | {item.get('匹配原因', '按顺序兜底匹配')} |\n"
    metrics_html = f"""
<div class=\"metric-grid\">
  <div class=\"metric\"><strong>{len(saved_videos)}</strong><span>视频素材</span></div>
  <div class=\"metric\"><strong>{len(saved_images)}</strong><span>图片素材</span></div>
  <div class=\"metric\"><strong>{len(library_items or [])}</strong><span>素材库调用</span></div>
  <div class=\"metric\"><strong>{len(storyboard)}</strong><span>AI分镜</span></div>
  <div class=\"metric\"><strong>{effective_duration}s</strong><span>成片时长</span></div>
</div>
    """

    video_result = str(video_path) if video_path else None
    markdown += f"\n\n**调试文件**：`{debug_path.name}`（用于核对字幕与配音文本）"
    return metrics_html + markdown, video_result, str(plan_path), video_result, gr.update(selected="result")


def show_generating_page() -> tuple[str, None, None, None, Any]:
    return "## 正在生成视频，请稍候...\n\n系统已经收到生成请求，正在处理素材、分镜、配音和视频合成。", None, None, None, gr.update(selected="result")


def safe_build_demo_plan(*args: Any) -> tuple[str, str | None, str, str | None, Any]:
    try:
        return build_demo_plan(*args)
    except Exception as exc:
        return f"生成失败：{exc}", None, "", None, gr.update(selected="result")


def load_sample_script(style: str) -> str:
    samples = {
        "政务/民生宣传": "政务服务超50万人，线上线下一体化服务持续提升群众获得感。就业帮扶覆盖重点群体，精准服务让政策更快抵达群众身边。数字化平台持续升级，让城市服务更高效、更温暖。",
        "产品介绍": "这是一款面向业务团队的智能工具，支持一键导入素材、自动理解文案、快速生成宣传视频。它能显著降低制作成本，让每个同事都能完成高质量内容创作。",
        "业务介绍": "我们围绕客户需求持续升级服务能力，通过数字化流程提升协同效率。平台沉淀业务经验，帮助团队更快响应、更稳交付、更好服务客户。",
        "汇报总结": "本阶段项目围绕效率提升、体验优化和能力沉淀持续推进。团队完成关键节点交付，形成可复用方案，并将在下一阶段扩大应用范围。",
    }
    return samples.get(style, samples["业务介绍"])


with gr.Blocks(css=CSS, title="AI全自动剪辑工具", theme=gr.themes.Soft(primary_hue="cyan", secondary_hue="violet"), fill_width=True) as demo:
    with gr.Row(elem_classes=["layout-row"]):
        with gr.Column(scale=1, min_width=190):
            with gr.Group(elem_classes=["sidebar"]):
                nav_home = gr.Button("首页", elem_classes=["nav-button", "active"])
                nav_library = gr.Button("素材管理", elem_classes=["nav-button"])
                nav_script = gr.Button("文案与分镜", elem_classes=["nav-button"])
                nav_settings = gr.Button("风格选择&参数设置", elem_classes=["nav-button"])
                generate_btn = gr.Button("一键成片", elem_classes=["sidebar-generate"])
        with gr.Column(scale=12):
            with gr.Tabs(selected="home", elem_classes=["workspace-tabs"]) as workspace_tabs:
                with gr.Tab("首页", id="home"):
                    gr.HTML(
                        """
                        <div class="page-title"><span>AI</span> 一键成片</div>
                        <div class="home-stage">
                          <div class="hero-card">
                            <h1>创意无限，一键成片</h1>
                            <p><strong>使用流程</strong>：素材管理 → 文案与分镜 → 参数设置 → 生成视频</p>
                            <div class="chip-row">
                              <span class="chip">素材管理</span><span class="chip">文案与分镜</span><span class="chip">风格参数</span><span class="chip">视频生成</span>
                            </div>
                          </div>
                        </div>
                        """
                    )

                with gr.Tab("素材管理", id="library"):
                    gr.HTML("<div class='module-title'>素材管理</div><div class='module-subtitle'>上传视频、图片、音乐素材，并选择本次生成需要使用的素材库内容。</div>")
                    with gr.Row(elem_classes=["wide-row"]):
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>上传视频素材</div>")
                                material_files = gr.File(label="上传视频素材", file_count="multiple", file_types=["video"], height=210)
                                gr.Markdown("<div class='step-title' style='margin-top:14px;'>上传图片素材</div>")
                                image_files = gr.File(label="上传图片素材", file_count="multiple", file_types=["image"], height=115)
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>上传音乐素材</div>")
                                custom_music = gr.File(label="上传自定义音乐（可选）", file_count="single", file_types=["audio"], height=210)
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>本次使用的素材库素材</div>")
                                gr.Markdown("<div class='step-desc'>勾选素材用于本次生成；勾选后点删除可从素材库移除。</div>")
                                library_items = gr.CheckboxGroup(label="素材库", choices=_library_choices(), value=[])
                                with gr.Row():
                                    refresh_library_btn = gr.Button("刷新素材库")
                                    delete_library_btn = gr.Button("删除选中素材", variant="stop")
                                gr.Markdown("<div class='step-title' style='margin-top:14px;'>上传素材到素材库</div>")
                                library_uploads = gr.File(label="上传素材：视频 / 图片 / BGM", file_count="multiple", file_types=["video", "image", "audio"], height=135)
                                save_library_btn = gr.Button("保存素材", variant="primary")
                                library_status = gr.Textbox(label="操作状态", lines=2, interactive=False)
                with gr.Tab("文案与分镜", id="script"):
                    gr.HTML("<div class='module-title'>文案与分镜</div><div class='module-subtitle'>输入宣传文案，或手动填写自定义分镜，系统会根据这里的内容生成脚本和画面匹配。</div>")
                    with gr.Row(elem_classes=["wide-row"]):
                        with gr.Column(scale=3):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>宣传文案</div>")
                                script = gr.Textbox(label="宣传文案 / 详细时间轴脚本", lines=18, placeholder="输入宣传文案，或粘贴包含时间轴、画面提示、口播文案的详细脚本...")
                                sample_btn = gr.Button("填入示例文案")
                        with gr.Column(scale=2):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>自定义分镜</div>")
                                custom_storyboard = gr.Textbox(
                                    label="自定义分镜（可选）",
                                    lines=18,
                                    placeholder="每行一个分镜，用 | 分隔：文案 | 时长秒 | 关键词 | 指定素材名 | 画面提示\n例如：\n这是一次AI语音测试 | 5 | 政务大厅、窗口 | hux1.jpg | 政务大厅近景",
                                )

                with gr.Tab("风格选择&参数设置", id="settings"):
                    gr.HTML("<div class='module-title'>风格选择&参数设置</div><div class='module-subtitle'>设置视频风格、目标时长、视频比例、配音风格与默认音乐。</div>")
                    with gr.Row(elem_classes=["wide-row"]):
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>视频风格与音乐</div>")
                                style = gr.Dropdown(label="视频类型", choices=list(STYLE_PRESETS.keys()), value="政务/民生宣传")
                                music_choice = gr.Dropdown(label="在线音乐库", choices=list(DEMO_MUSIC.keys()), value="企业宣传｜稳重科技感")
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>成片参数</div>")
                                target_duration = gr.Slider(label="目标视频时长（秒）", minimum=15, maximum=90, step=5, value=30)
                                aspect_ratio = gr.Radio(label="画面比例", choices=["16:9 横版", "9:16 竖版", "1:1 方版"], value="16:9 横版")
                                voice_style = gr.Radio(label="配音风格", choices=["正式新闻播报", "温暖亲和女声", "沉稳商务男声", "年轻活力"], value="温暖亲和女声")

                with gr.Tab("生成视频", id="result"):
                    with gr.Row(elem_classes=["wide-row"]):
                        with gr.Column(scale=4):
                            gr.HTML("<div class='module-title'>生成视频</div><div class='module-subtitle'>成片生成完成后，可直接预览。</div>")
                        with gr.Column(scale=2):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("<div class='step-title'>下载区</div>")
                                with gr.Row():
                                    video_file = gr.File(label="下载视频", elem_classes=["file-btn"])
                                    plan_file = gr.File(label="下载分镜", elem_classes=["file-btn"])
                    with gr.Row(elem_classes=["wide-row"]):
                        with gr.Column(scale=3):
                            with gr.Group(elem_classes=["result-card"]):
                                output_video = gr.Video(label="视频预览", height=520)
                        with gr.Column(scale=2):
                            with gr.Group(elem_classes=["result-card"]):
                                result_md = gr.Markdown(label="分镜结果")
    gr.HTML("<div class='footer-note'>建议演示时使用 20～30 秒视频、4～6 张图片素材，避免多人同时生成。</div>")

    scroll_top_js = """() => {
        requestAnimationFrame(() => {
            window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            const containers = document.querySelectorAll('.main-panel, .gradio-container, main, .contain, .wrap, .app-shell');
            containers.forEach((el) => { el.scrollTop = 0; });
        });
    }"""

    sample_btn.click(fn=load_sample_script, inputs=[style], outputs=[script])
    nav_home.click(fn=lambda: gr.update(selected="home"), inputs=None, outputs=[workspace_tabs], js=scroll_top_js)
    nav_library.click(fn=lambda: gr.update(selected="library"), inputs=None, outputs=[workspace_tabs], js=scroll_top_js)
    nav_script.click(fn=lambda: gr.update(selected="script"), inputs=None, outputs=[workspace_tabs], js=scroll_top_js)
    nav_settings.click(fn=lambda: gr.update(selected="settings"), inputs=None, outputs=[workspace_tabs], js=scroll_top_js)
    save_library_btn.click(fn=save_to_material_library, inputs=[library_uploads], outputs=[library_items, library_status])
    refresh_library_btn.click(fn=refresh_material_library, inputs=None, outputs=[library_items])
    delete_library_btn.click(fn=delete_from_material_library, inputs=[library_items], outputs=[library_items, library_status])
    generate_event = generate_btn.click(
        fn=show_generating_page,
        inputs=None,
        outputs=[result_md, output_video, plan_file, video_file, workspace_tabs],
        js=scroll_top_js,
    )
    generate_event.then(
        fn=safe_build_demo_plan,
        inputs=[material_files, image_files, script, music_choice, custom_music, style, target_duration, voice_style, aspect_ratio, custom_storyboard, library_items],
        outputs=[result_md, output_video, plan_file, video_file, workspace_tabs],
    )
if __name__ == "__main__":
    server_config = get_app_config().server
    demo.launch(
        server_name=server_config.name,
        server_port=server_config.port,
        inbrowser=server_config.inbrowser,
        share=server_config.share,
    )