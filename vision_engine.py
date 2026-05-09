from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import requests

from api_config import get_app_config

SCENE_KEYWORDS = {
    "政务": ["政务", "大厅", "窗口", "办事", "便民", "公安", "交警", "服务中心"],
    "就业": ["就业", "招聘", "岗位", "求职", "人才", "企业", "帮扶"],
    "数据": ["数据", "大屏", "平台", "系统", "数字", "看板", "智能", "科技"],
    "群众": ["群众", "市民", "居民", "用户", "客户", "人员", "服务"],
    "产品": ["产品", "界面", "功能", "演示", "操作", "截图", "流程"],
    "汇报": ["会议", "汇报", "团队", "项目", "成果", "办公室", "讨论"],
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _normalize(text: str) -> str:
    return text.lower().replace(" ", "").replace("_", "").replace("-", "")


def _local_tags(path: Path) -> list[str]:
    text = _normalize(path.stem)
    tags: list[str] = []
    for label, keywords in SCENE_KEYWORDS.items():
        if any(_normalize(keyword) in text for keyword in keywords):
            tags.append(label)
            tags.extend(keywords[:3])
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        tags.append("图片素材")
    elif path.suffix.lower() in VIDEO_EXTENSIONS:
        tags.append("视频素材")
    if not tags:
        tags.append("通用素材")
    unique: list[str] = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    return unique


def _image_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix == "jpg" else suffix
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/{mime};base64,{encoded}"


def _parse_tags_from_text(text: str) -> list[str]:
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            raw_tags = value.get("tags") or value.get("标签") or []
        elif isinstance(value, list):
            raw_tags = value
        else:
            raw_tags = []
    except json.JSONDecodeError:
        raw_tags = [part.strip() for part in text.replace("，", ",").replace("、", ",").split(",")]
    tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    return tags[:12]


def _openai_compatible_image_tags(path: Path) -> tuple[list[str], str]:
    config = get_app_config().vision
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return _local_tags(path), "视觉 API 暂只分析图片，视频素材使用本地文件名标签。"
    if not config.api_key or not config.base_url or not config.model:
        return _local_tags(path), "视觉 API 配置不完整，使用本地文件名标签。"
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张素材图，返回 JSON：{\"tags\":[\"标签1\",\"标签2\"]}。标签用于短视频素材匹配，尽量包含场景、人物、物体、风格。"},
                    {"type": "image_url", "image_url": {"url": _image_to_data_url(path)}},
                ],
            }
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return _local_tags(path), f"视觉 API 调用失败，使用本地文件名标签：{exc}"
    tags = _parse_tags_from_text(content)
    if not tags:
        return _local_tags(path), "视觉 API 未返回有效标签，使用本地文件名标签。"
    return tags, f"已使用视觉 API 分析素材：{path.name}。"


def analyze_material_tags(material_paths: list[Path]) -> tuple[dict[str, list[str]], str]:
    provider = get_app_config().vision.provider
    if not material_paths:
        return {}, "未上传素材，跳过视觉标签分析。"
    tag_map: dict[str, list[str]] = {}
    messages: list[str] = []
    use_api = provider in {"openai", "openai-compatible", "compatible"}
    for path in material_paths:
        if use_api:
            tags, message = _openai_compatible_image_tags(path)
            messages.append(message)
        else:
            tags = _local_tags(path)
        tag_map[path.name] = tags
    if use_api:
        failed = sum(1 for message in messages if "失败" in message or "不完整" in message or "未返回" in message)
        return tag_map, f"素材标签分析完成：{len(tag_map)} 个素材，其中 {failed} 个使用本地兜底。"
    return tag_map, f"未启用视觉 API，已根据文件名为 {len(tag_map)} 个素材生成本地标签。"
