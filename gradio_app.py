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

CAMERA_PRESETS = [
    "自动运镜",
    "缓慢推近",
    "缓慢拉远",
    "从左到右",
    "从右到左",
    "从上到下",
    "从下到上",
    "固定镜头",
]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

STYLE_PRESETS = {
    "政务/民生宣传": ["政务大厅", "办事窗口", "工作人员", "群众", "服务", "数据大屏", "城市", "政策"],
    "产品介绍": ["产品界面", "功能演示", "用户操作", "数据看板", "效率提升", "解决方案"],
    "业务介绍": ["团队协作", "客户沟通", "业务流程", "办公场景", "数字化", "成果展示"],
    "汇报总结": ["会议", "数据图表", "项目成果", "团队", "里程碑", "未来规划"],
}

CSS = """
:root {
  --primary: #1677ff;
  --primary-dark: #0f4fd6;
  --ink: #111827;
  --muted: #6b7280;
  --card: rgba(255, 255, 255, 0.86);
}
.gradio-container {
  max-width: 1280px !important;
  margin: 0 auto !important;
  background:
    radial-gradient(circle at 10% 10%, rgba(22, 119, 255, 0.16), transparent 30%),
    radial-gradient(circle at 90% 0%, rgba(114, 46, 209, 0.14), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4ff 45%, #f8fafc 100%);
}
.hero {
  padding: 34px 34px 26px;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(15, 79, 214, 0.96), rgba(22, 119, 255, 0.9) 48%, rgba(114, 46, 209, 0.88));
  color: white;
  box-shadow: 0 24px 70px rgba(22, 119, 255, 0.24);
  margin-bottom: 20px;
}
.hero h1 {
  font-size: 38px;
  line-height: 1.16;
  margin: 0 0 12px;
  letter-spacing: -0.04em;
}
.hero p {
  font-size: 16px;
  opacity: 0.94;
  max-width: 860px;
  margin: 0;
}
.badges {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
}
.badge {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.16);
  border: 1px solid rgba(255,255,255,0.24);
  font-size: 13px;
}
.section-card, .panel, .block, .form {
  border-radius: 22px !important;
}
.step-title {
  font-weight: 700;
  font-size: 18px;
  color: var(--ink);
  margin: 8px 0 2px;
}
.step-desc {
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 10px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0;
}
.metric {
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(148,163,184,0.22);
  border-radius: 18px;
  padding: 14px;
}
.metric strong { display: block; font-size: 21px; color: #0f4fd6; }
.metric span { color: #64748b; font-size: 12px; }
.footer-note {
  color: #64748b;
  font-size: 12px;
  text-align: center;
  margin-top: 18px;
}
button.primary, .primary button {
  background: linear-gradient(135deg, #1677ff, #722ed1) !important;
  border: none !important;
}
@media (max-width: 900px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero h1 { font-size: 28px; }
}
"""


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
    files = [path for path in LIBRARY_DIR.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS]
    return [path.name for path in sorted(files, key=lambda item: item.name.lower())]


def _copy_library_items(names: list[str] | None, target_dir: Path) -> tuple[list[Path], list[Path]]:
    saved_videos: list[Path] = []
    saved_images: list[Path] = []
    if not names:
        return saved_videos, saved_images
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
    return saved_videos, saved_images


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


def refresh_material_library() -> gr.CheckboxGroup:
    return gr.CheckboxGroup(choices=_library_choices(), value=[])


def _parse_camera_plan(camera_mode: str, custom_camera: str, storyboard_count: int) -> list[str]:
    if storyboard_count <= 0:
        return []
    if camera_mode != "自定义运镜":
        return [camera_mode] * storyboard_count

    lines = [line.strip() for line in custom_camera.replace("；", "\n").replace(";", "\n").splitlines() if line.strip()]
    parsed: list[str] = []
    for line in lines:
        if ":" in line:
            line = line.split(":", 1)[1].strip()
        if "：" in line:
            line = line.split("：", 1)[1].strip()
        parsed.append(line)
    if not parsed:
        return ["自动运镜"] * storyboard_count
    return [parsed[index] if index < len(parsed) else parsed[-1] for index in range(storyboard_count)]


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
            voice_text = block.strip()
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
        text = parts[0]
        duration_text = parts[1]
        camera = parts[2] if len(parts) > 2 and parts[2] else "自动运镜"
        keywords = [item.strip() for item in re.split(r"[、,，/]", parts[3])] if len(parts) > 3 and parts[3] else _mock_match(text, "业务介绍")
        material_hint = parts[4] if len(parts) > 4 else ""
        visual_prompt = parts[5] if len(parts) > 5 else ""
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
    matched = []
    for keyword in preset:
        if keyword[:2] in sentence or keyword in sentence:
            matched.append(keyword)
    if not matched:
        lower_sentence = sentence.lower()
        for keyword in preset:
            if any(token in lower_sentence for token in ["服务", "产品", "数据", "业务", "群众", "就业", "政务", "汇报"]):
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
    camera_mode: str,
    custom_camera: str,
    custom_storyboard: str,
    library_items: list[str] | None,
) -> tuple[str, str, str, str | None, str | None]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"demo_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    saved_videos = _save_uploads(materials, run_dir / "materials")
    saved_images = _save_uploads(images, run_dir / "images")
    library_videos, library_images = _copy_library_items(library_items, run_dir / "library_materials")
    saved_videos.extend(library_videos)
    saved_images.extend(library_images)
    custom_music_path = None
    if custom_music is not None:
        music_files = _save_uploads([custom_music], run_dir / "music")
        custom_music_path = music_files[0] if music_files else None

    if not script.strip() and not (custom_storyboard or "").strip():
        return "请先输入宣传文案或自定义分镜。", "", "", None, None

    custom_storyboard_items = _parse_custom_storyboard(custom_storyboard or "")
    if custom_storyboard_items:
        timeline_storyboard = []
        tts_script = "".join(item["文案"] for item in custom_storyboard_items)
    else:
        timeline_storyboard, voice_script = _parse_timeline_script(script)
        tts_script = voice_script if timeline_storyboard else script
    voice_path, voice_message = synthesize_tts(tts_script, run_dir, voice_style)
    real_voice_duration = get_audio_duration(voice_path)
    storyboard_message = ""
    effective_duration = max(target_duration, int(real_voice_duration + 1.5), int(estimate_voice_duration(tts_script, 0)))
    if custom_storyboard_items:
        storyboard = custom_storyboard_items
        effective_duration = max(effective_duration, int(sum(float(str(item["建议时长"]).replace("秒", "")) for item in storyboard)))
    elif timeline_storyboard:
        storyboard = timeline_storyboard
        effective_duration = max(effective_duration, int(sum(float(str(item["建议时长"]).replace("秒", "")) for item in storyboard)))
        camera_plan = _parse_camera_plan(camera_mode, custom_camera, len(storyboard))
        if camera_mode != "自动运镜":
            for index, item in enumerate(storyboard):
                item["运镜方式"] = camera_plan[index] if index < len(camera_plan) else "自动运镜"
    else:
        storyboard, storyboard_message = generate_storyboard(script, style, effective_duration)
        camera_plan = _parse_camera_plan(camera_mode, custom_camera, len(storyboard))
        if camera_mode != "自动运镜":
            for index, item in enumerate(storyboard):
                item["运镜方式"] = camera_plan[index] if index < len(camera_plan) else item.get("运镜方式", "自动运镜")
    all_materials = saved_images + saved_videos
    material_tags, vision_message = analyze_material_tags(all_materials)
    storyboard = assign_materials_to_storyboard(storyboard, all_materials, material_tags)

    selected_music_path, selected_music, music_source = _resolve_music_path(music_choice, custom_music_path)
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
        "运镜模式": camera_mode,
        "分镜数量": len(storyboard),
    }

    plan_path = run_dir / "storyboard_plan.json"
    plan_path.write_text(json.dumps({"summary": summary, "storyboard": storyboard}, ensure_ascii=False, indent=2), encoding="utf-8")

    video_path = None
    video_error = ""
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
    except Exception as exc:
        video_error = f"基础视频生成失败：{exc}"

    markdown = "## AI 分镜与镜头匹配预览\n\n"
    if custom_storyboard_items:
        markdown += "| 句子 | 建议时长 | 运镜方式 | 画面关键词 | 自定义素材 | 匹配素材 | 匹配说明 |\n|---|---:|---|---|---|---|---|\n"
        for item in storyboard:
            markdown += f"| {item['文案']} | {item['建议时长']} | {item.get('运镜方式', '自动运镜')} | {'、'.join(item['画面关键词'])} | {item.get('自定义素材', '')} | {item.get('匹配素材', '模板背景')} | {item.get('匹配原因', '按自定义分镜匹配')} |\n"
    elif timeline_storyboard:
        markdown += "| 时间轴 | 口播文案 | 建议时长 | 运镜方式 | 画面提示 | 人物/特效 | 匹配素材 |\n|---|---|---:|---|---|---|---|\n"
        for item in storyboard:
            visual = str(item.get("画面提示", ""))[:90].replace("|", "/")
            effect = str(item.get("人物状态/特效", ""))[:60].replace("|", "/")
            markdown += f"| {item.get('时间轴', '')} | {item['文案']} | {item['建议时长']} | {item.get('运镜方式', '自动运镜')} | {visual} | {effect} | {item.get('匹配素材', '模板背景')} |\n"
    else:
        markdown += "| 句子 | 建议时长 | 运镜方式 | 画面关键词 | 匹配素材 | 匹配说明 |\n|---|---:|---|---|---|---|\n"
        for item in storyboard:
            markdown += f"| {item['文案']} | {item['建议时长']} | {item.get('运镜方式', '自动运镜')} | {'、'.join(item['画面关键词'])} | {item.get('匹配素材', '模板背景')} | {item.get('匹配原因', '按顺序兜底匹配')} |\n"
    log = [
        "已完成 AI 分镜方案。",
        f"脚本解析模式：{'自定义分镜' if custom_storyboard_items else ('详细时间轴脚本' if timeline_storyboard else 'LLM/本地增强分镜')}。",
        f"素材已保存到：{run_dir}",
        f"分镜方案已生成：{plan_path.name}",
        "已完成文案-素材轻量匹配：优先根据文件名关键词选择镜头。",
        vision_message,
        storyboard_message or "当前分镜来自用户自定义/时间轴脚本。",
        f"已应用运镜方案：{camera_mode}。",
        f"旁白真实时长：{real_voice_duration:.1f}秒；最终成片时长：{effective_duration}秒。",
        voice_message,
        "正在生成带旁白的基础演示视频...",
    ]

    if video_path:
        log.append(f"基础演示视频已生成：{video_path.name}")
        if music_source == "custom":
            log.append("已添加上传的 BGM，并自动降低背景音量。")
        elif music_source == "library":
            log.append(f"已添加默认音乐库 BGM：{selected_music}，并自动降低背景音量。")
        elif music_source == "missing":
            log.append(f"已选择默认音乐「{music_choice}」，但 assets/music 中缺少对应文件，未添加 BGM。")
        else:
            log.append("已选择暂不添加音乐，本次生成无 BGM。")
    else:
        log.append(video_error or "基础演示视频未生成。")
    log.append("后续可替换为公司高质量 TTS API，提升音色自然度和情绪表现。")

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
    return metrics_html + markdown, "\n".join(log), str(plan_path), video_result, video_result


def load_sample_script(style: str) -> str:
    samples = {
        "政务/民生宣传": "政务服务超50万人，线上线下一体化服务持续提升群众获得感。就业帮扶覆盖重点群体，精准服务让政策更快抵达群众身边。数字化平台持续升级，让城市服务更高效、更温暖。",
        "产品介绍": "这是一款面向业务团队的智能工具，支持一键导入素材、自动理解文案、快速生成宣传视频。它能显著降低制作成本，让每个同事都能完成高质量内容创作。",
        "业务介绍": "我们围绕客户需求持续升级服务能力，通过数字化流程提升协同效率。平台沉淀业务经验，帮助团队更快响应、更稳交付、更好服务客户。",
        "汇报总结": "本阶段项目围绕效率提升、体验优化和能力沉淀持续推进。团队完成关键节点交付，形成可复用方案，并将在下一阶段扩大应用范围。",
    }
    return samples.get(style, samples["业务介绍"])


with gr.Blocks(css=CSS, title="AI全自动剪辑工具", theme=gr.themes.Soft(primary_hue="blue", secondary_hue="purple")) as demo:
    gr.HTML(
        """
        <div class="hero">
          <h1>AI 一键成片工具</h1>
          <p>上传旧视频或只上传图片，输入新文案，选择音乐、素材库与运镜方式，点击一次即可自动规划分镜、生成旁白、匹配画面、烧录字幕并导出基础宣传片。当前已支持本地离线配音、素材库复用与自定义运镜，适合比赛现场演示“一键成片”核心能力。</p>
          <div class="badges">
            <span class="badge">图片动态成片</span>
            <span class="badge">文案驱动分镜</span>
            <span class="badge">自动旁白配音</span>
            <span class="badge">BGM 智能混音</span>
            <span class="badge">详细脚本解析</span>
            <span class="badge">素材库复用</span>
            <span class="badge">自定义运镜</span>
            <span class="badge">本地演示版</span>
          </div>
        </div>
        """
    )

    with gr.Row():
        with gr.Column(scale=5):
            gr.Markdown("<div class='step-title'>1. 上传素材</div><div class='step-desc'>可以只上传图片，也可以上传视频和图片混合素材。图片会自动生成推近、平移等动态镜头。</div>")
            material_files = gr.File(label="上传视频素材", file_count="multiple", file_types=["video"], height=140)
            image_files = gr.File(label="上传图片素材", file_count="multiple", file_types=["image"], height=120)

            with gr.Accordion("素材库（可复用素材）", open=False):
                library_uploads = gr.File(label="加入素材库：图片/视频", file_count="multiple", file_types=["image", "video"], height=110)
                gr.Markdown("素材库会保存到 `assets/library`，以后每次打开工具都可以复用；你也可以直接把常用素材复制到这个文件夹后点击刷新。")
                with gr.Row():
                    save_library_btn = gr.Button("保存到素材库")
                    refresh_library_btn = gr.Button("刷新素材库")
                library_items = gr.CheckboxGroup(label="本次使用的素材库素材", choices=_library_choices(), value=[])
                library_status = gr.Textbox(label="素材库状态", lines=2, interactive=False)

            gr.Markdown("<div class='step-title'>2. 输入文案与选择风格</div><div class='step-desc'>支持普通宣传文案，也支持包含 0:00-0:15 这类时间轴的详细脚本；详细脚本会只提取口播文案用于配音，画面 Prompt 用于素材匹配。</div>")
            style = gr.Dropdown(label="视频类型", choices=list(STYLE_PRESETS.keys()), value="政务/民生宣传")
            script = gr.Textbox(label="宣传文案 / 详细时间轴脚本", lines=10, placeholder="可以输入普通文案，也可以粘贴包含 0:00-0:15、画面提示、人物状态/特效、口播文案的完整脚本...")
            sample_btn = gr.Button("填入示例文案")

        with gr.Column(scale=4):
            gr.Markdown("<div class='step-title'>3. 选择音乐、运镜与生成参数</div><div class='step-desc'>可以统一选择运镜，也可以按分镜逐行自定义；图片素材会按运镜生成动态镜头。</div>")
            music_choice = gr.Dropdown(label="在线音乐库", choices=list(DEMO_MUSIC.keys()), value="企业宣传｜稳重科技感")
            custom_music = gr.File(label="上传自定义音乐（可选）", file_count="single", file_types=["audio"])
            target_duration = gr.Slider(label="目标视频时长（秒）", minimum=15, maximum=90, step=5, value=30)
            aspect_ratio = gr.Radio(label="画面比例", choices=["16:9 横版", "9:16 竖版", "1:1 方版"], value="16:9 横版")
            camera_mode = gr.Dropdown(label="运镜方式", choices=CAMERA_PRESETS + ["自定义运镜"], value="自动运镜")
            custom_camera = gr.Textbox(
                label="自定义运镜（选择自定义时生效）",
                lines=4,
                placeholder="每行对应一个分镜，例如：\n1：缓慢推近\n2：从左到右\n3：固定镜头",
            )
            voice_style = gr.Radio(label="配音风格", choices=["正式新闻播报", "温暖亲和女声", "沉稳商务男声", "年轻活力"], value="正式新闻播报")
            custom_storyboard = gr.Textbox(
                label="自定义分镜（可选，优先级高于自动分镜）",
                lines=6,
                placeholder="每行一个分镜，用 | 分隔：文案 | 时长秒 | 运镜 | 关键词 | 指定素材名 | 画面提示\n例如：\n这是一次AI语音测试 | 5 | 缓慢推近 | 政务大厅、窗口 | hux1.jpg | 政务大厅近景\n系统将自动生成旁白和字幕 | 10 | 从左到右 | 工作人员、群众 | hux2.jpg | 办事窗口服务画面",
            )
            generate_btn = gr.Button("AI 一键成片", variant="primary", elem_classes=["primary"])

    with gr.Row():
        with gr.Column(scale=6):
            result_md = gr.Markdown(label="AI 分镜结果")
            output_video = gr.Video(label="生成视频预览", height=420)
        with gr.Column(scale=3):
            log_box = gr.Textbox(label="运行日志", lines=12)
            plan_file = gr.File(label="下载分镜 JSON")
            video_file = gr.File(label="下载生成视频")

    gr.HTML("<div class='footer-note'>展示版定位：本地单机打开，不上线，不多人并发；当前支持图片/视频一键生成带旁白、字幕和 BGM 的基础成片。</div>")

    sample_btn.click(fn=load_sample_script, inputs=[style], outputs=[script])
    save_library_btn.click(fn=save_to_material_library, inputs=[library_uploads], outputs=[library_items, library_status])
    refresh_library_btn.click(fn=refresh_material_library, inputs=None, outputs=[library_items])
    generate_btn.click(
        fn=build_demo_plan,
        inputs=[material_files, image_files, script, music_choice, custom_music, style, target_duration, voice_style, aspect_ratio, camera_mode, custom_camera, custom_storyboard, library_items],
        outputs=[result_md, log_box, plan_file, output_video, video_file],
    )


if __name__ == "__main__":
    server_config = get_app_config().server
    demo.launch(
        server_name=server_config.name,
        server_port=server_config.port,
        inbrowser=server_config.inbrowser,
        share=server_config.share,
    )