from __future__ import annotations

import json
import re
from typing import Any

import requests

from api_config import get_app_config
from matching_engine import sentence_keywords

STYLE_KEYWORDS = {
    "政务/民生宣传": ["政务大厅", "办事窗口", "工作人员", "群众", "服务", "数据大屏", "城市", "政策"],
    "产品介绍": ["产品界面", "功能演示", "用户操作", "数据看板", "效率提升", "解决方案"],
    "业务介绍": ["团队协作", "客户沟通", "业务流程", "办公场景", "数字化", "成果展示"],
    "汇报总结": ["会议", "数据图表", "项目成果", "团队", "里程碑", "未来规划"],
}

CAMERA_SUGGESTIONS = ["缓慢推近", "从右到左", "从左到右", "从上到下", "固定镜头", "缓慢拉远"]


def extract_script_topics(script: str, style: str, limit: int = 6) -> list[str]:
    topic_text = sentence_keywords(script, STYLE_KEYWORDS.get(style, []))
    topics: list[str] = []
    for item in topic_text:
        if item not in topics:
            topics.append(item)
    if not topics:
        topics = STYLE_KEYWORDS.get(style, STYLE_KEYWORDS["业务介绍"])
    return topics[:limit]


def split_script_sentences(script: str) -> list[str]:
    normalized = script.replace("；", "。")
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    rough: list[str] = []
    for line in lines or [normalized]:
        parts = [item.strip(" ，,。！？!?；;\t") for item in re.split(r"[。！？!?；;]", line)]
        rough.extend([item for item in parts if item])

    # 合并过短口语句，避免“没错”这类单独成句
    merged: list[str] = []
    for part in rough:
        if len(part) <= 3 and merged:
            merged[-1] = f"{merged[-1]}，{part}"
        else:
            merged.append(part)
    return merged


def local_keywords(sentence: str, style: str) -> list[str]:
    preset = STYLE_KEYWORDS.get(style, STYLE_KEYWORDS["业务介绍"])

    phrase_candidates = re.findall(r"[\u4e00-\u9fff]{2,8}", sentence)
    stop_words = {"我们", "你们", "他们", "这个", "那个", "进行", "实现", "推进", "持续", "提升", "更加", "通过", "以及", "就是", "没错"}
    dynamic_terms: list[str] = []
    for phrase in phrase_candidates:
        token = phrase.strip()
        if not token or token in stop_words or token in dynamic_terms:
            continue
        dynamic_terms.append(token)
        if len(dynamic_terms) >= 4:
            break

    candidates = sentence_keywords(sentence, preset)
    filtered: list[str] = []
    generic = {"政务", "服务", "城市", "群众", "产品", "数据", "平台", "科技", "创新"}

    # 先放句内动态词，再补候选词，尽量避免每句都一样
    for item in dynamic_terms + [str(x).strip() for x in candidates]:
        token = str(item).strip()
        if not token or token in filtered:
            continue
        if token in generic and len(filtered) >= 2:
            continue
        filtered.append(token)
        if len(filtered) >= 6:
            break

    if not filtered:
        filtered = extract_script_topics(sentence, style, limit=6)
    return filtered[:4] if filtered else preset[:4]


def local_storyboard(script: str, style: str, target_duration: int) -> tuple[list[dict[str, Any]], str]:
    sentences = split_script_sentences(script)
    if not sentences:
        return [], "本地规则未识别到有效句子。"
    total_chars = sum(max(len(sentence), 1) for sentence in sentences)
    storyboard: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences, start=1):
        weight = max(len(sentence), 1) / total_chars
        duration = max(2.0, round(target_duration * weight, 1))
        keywords = local_keywords(sentence, style)
        camera = CAMERA_SUGGESTIONS[(index - 1) % len(CAMERA_SUGGESTIONS)]
        storyboard.append(
            {
                "序号": index,
                "文案": sentence,
                "建议时长": f"{duration}秒",
                "画面关键词": keywords,
                "运镜方式": camera,
                "镜头建议": f"优先匹配：{' / '.join(keywords)}；素材不足时使用同风格通用镜头兜底。",
                "分镜来源": "本地规则",
            }
        )
    return storyboard, "未启用 LLM，已使用本地规则生成分镜。"


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(text)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict) and isinstance(value.get("storyboard"), list):
            return [item for item in value["storyboard"] if isinstance(item, dict)]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _normalize_llm_storyboard(items: list[dict[str, Any]], style: str, target_duration: int) -> list[dict[str, Any]]:
    if not items:
        return []
    fallback_duration = max(2.0, round(target_duration / max(len(items), 1), 1))
    storyboard: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        text = str(item.get("文案") or item.get("口播文案") or item.get("sentence") or "").strip()
        if not text:
            continue
        raw_duration = str(item.get("建议时长") or item.get("duration") or fallback_duration).replace("秒", "")
        try:
            duration = max(1.0, float(raw_duration))
        except ValueError:
            duration = fallback_duration
        raw_keywords = item.get("画面关键词") or item.get("keywords") or local_keywords(text, style)
        if isinstance(raw_keywords, str):
            keywords = [part.strip() for part in re.split(r"[、,，/]", raw_keywords) if part.strip()]
        elif isinstance(raw_keywords, list):
            keywords = [str(part).strip() for part in raw_keywords if str(part).strip()]
        else:
            keywords = local_keywords(text, style)
        storyboard.append(
            {
                "序号": index,
                "文案": text,
                "建议时长": f"{duration}秒",
                "画面关键词": keywords[:6] or local_keywords(text, style),
                "运镜方式": str(item.get("运镜方式") or item.get("camera") or CAMERA_SUGGESTIONS[(index - 1) % len(CAMERA_SUGGESTIONS)]),
                "画面提示": str(item.get("画面提示") or item.get("visual_prompt") or ""),
                "镜头建议": str(item.get("镜头建议") or item.get("shot_suggestion") or "按 LLM 分镜建议匹配素材。"),
                "分镜来源": "LLM",
            }
        )
    return storyboard


def _build_prompt(script: str, style: str, target_duration: int) -> str:
    return f"""
你是一个短视频分镜策划师。请把用户文案拆成适合剪辑的分镜 JSON 数组。
要求：
1. 只返回 JSON，不要解释。
2. 每个元素包含：文案、建议时长、画面关键词、运镜方式、画面提示、镜头建议。
3. 建议时长单位是秒，所有分镜总时长尽量接近 {target_duration} 秒。
4. 视频类型：{style}。
5. 画面关键词适合用于匹配素材文件名。

用户文案：
{script}
""".strip()


def _openai_compatible_storyboard(script: str, style: str, target_duration: int) -> tuple[list[dict[str, Any]], str]:
    config = get_app_config().llm
    if not config.api_key or not config.base_url or not config.model:
        return [], "LLM 配置不完整，已回退到本地规则分镜。"
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "你是专业短视频剪辑分镜助手，只输出 JSON。"},
            {"role": "user", "content": _build_prompt(script, style, target_duration)},
        ],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        return [], f"LLM 分镜调用失败，已回退到本地规则：{exc}"
    storyboard = _normalize_llm_storyboard(_extract_json_array(content), style, target_duration)
    if not storyboard:
        return [], "LLM 未返回有效分镜，已回退到本地规则。"
    return storyboard, f"已使用 LLM 生成专业分镜：{config.provider}/{config.model}。"


def generate_storyboard(script: str, style: str, target_duration: int) -> tuple[list[dict[str, Any]], str]:
    provider = get_app_config().llm.provider
    if provider in {"none", "off", "disabled", "local"}:
        return local_storyboard(script, style, target_duration)
    if provider in {"openai", "openai-compatible", "compatible"}:
        storyboard, message = _openai_compatible_storyboard(script, style, target_duration)
        if storyboard:
            return storyboard, message
        fallback, fallback_message = local_storyboard(script, style, target_duration)
        return fallback, f"{message}\n{fallback_message}"
    fallback, fallback_message = local_storyboard(script, style, target_duration)
    return fallback, f"未知 LLM_PROVIDER：{provider}，已回退到本地规则。\n{fallback_message}"
