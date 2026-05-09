from __future__ import annotations

from pathlib import Path
from typing import Any

SCENE_KEYWORDS = {
    "政务": ["政务", "大厅", "窗口", "办事", "便民", "公安", "交警", "服务中心"],
    "就业": ["就业", "招聘", "岗位", "求职", "人才", "企业", "帮扶"],
    "数据": ["数据", "大屏", "平台", "系统", "数字", "看板", "智能", "科技"],
    "群众": ["群众", "市民", "居民", "用户", "客户", "人员", "服务"],
    "产品": ["产品", "界面", "功能", "演示", "操作", "截图", "流程"],
    "汇报": ["会议", "汇报", "团队", "项目", "成果", "办公室", "讨论"],
}


def normalize_text(text: str) -> str:
    return text.lower().replace(" ", "").replace("_", "").replace("-", "")


def material_label(path: Path, material_tags: dict[str, list[str]] | None = None) -> str:
    if material_tags and material_tags.get(path.name):
        return "、".join(material_tags[path.name][:6])
    name = normalize_text(path.stem)
    labels = []
    for _label, keywords in SCENE_KEYWORDS.items():
        if any(keyword.lower() in name for keyword in keywords):
            labels.append(_label)
    return "、".join(labels) if labels else "通用素材"


def sentence_keywords(sentence: str, visual_keywords: list[str]) -> list[str]:
    text = normalize_text(sentence + "".join(visual_keywords))
    matched: list[str] = []
    priority_terms = [
        "峰会", "展会", "入口", "注册", "导览", "展台", "政务", "助手", "智慧", "服务",
        "平台", "城市", "治理", "民生", "科技", "创新", "支付", "生活", "群众", "办事",
        "体验", "互动", "团队", "产品", "展示", "未来", "全景", "合影", "讲解", "签到", "路演",
    ]
    for term in priority_terms:
        if term in text and term not in matched:
            matched.append(term)
    for _label, keywords in SCENE_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            for kw in keywords[:3]:
                if kw not in matched:
                    matched.append(kw)
            if _label not in matched:
                matched.append(_label)
    for keyword in visual_keywords:
        if keyword not in matched:
            matched.append(keyword)
    return matched[:8] if matched else visual_keywords[:4]


def score_material(sentence: str, visual_keywords: list[str], path: Path, material_tags: dict[str, list[str]] | None = None) -> int:
    name = normalize_text(path.stem)
    tag_text = normalize_text("".join(material_tags.get(path.name, []))) if material_tags else ""
    keys = sentence_keywords(sentence, visual_keywords)
    score = 0
    for keyword in keys:
        key = normalize_text(keyword)
        if key and key in name:
            score += 3
        if key and key in tag_text:
            score += 5
    for _label, keywords in SCENE_KEYWORDS.items():
        label_hit_sentence = any(keyword in normalize_text(sentence) for keyword in keywords)
        label_hit_name = any(keyword in name for keyword in keywords)
        label_hit_tags = any(normalize_text(keyword) in tag_text for keyword in keywords)
        if label_hit_sentence and label_hit_name:
            score += 5
        if label_hit_sentence and label_hit_tags:
            score += 7
    return score


def _find_custom_material(material_paths: list[Path], material_hint: str) -> Path | None:
    hint = normalize_text(material_hint)
    if not hint:
        return None
    for path in material_paths:
        if normalize_text(path.name) == hint or normalize_text(path.stem) == hint:
            return path
    for path in material_paths:
        normalized_name = normalize_text(path.name)
        normalized_stem = normalize_text(path.stem)
        if hint in normalized_name or hint in normalized_stem or normalized_stem in hint:
            return path
    return None


def _content_tokens(sentence: str, visual_keywords: list[str]) -> list[str]:
    tokens = sentence_keywords(sentence, visual_keywords)
    priority = [token for token in tokens if len(token) <= 6]
    return priority[:8] if priority else tokens[:8]


def assign_materials_to_storyboard(
    storyboard: list[dict[str, Any]],
    material_paths: list[Path],
    material_tags: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    if not material_paths:
        for item in storyboard:
            item["匹配素材"] = "模板背景"
            item["匹配原因"] = "未上传素材，使用系统渐变模板兜底。"
        return storyboard

    used: set[Path] = set()
    for index, item in enumerate(storyboard):
        custom_material = _find_custom_material(material_paths, str(item.get("自定义素材", "")))
        if custom_material:
            used.add(custom_material)
            item["匹配素材"] = custom_material.name
            item["匹配原因"] = f"按自定义分镜指定素材「{item.get('自定义素材', '')}」强制匹配。"
            continue

        sentence = str(item.get("文案", ""))
        visual_keywords = list(item.get("画面关键词", []))
        content_tokens = _content_tokens(sentence, visual_keywords)
        ranked = sorted(
            material_paths,
            key=lambda path: (score_material(sentence, content_tokens, path, material_tags), path not in used),
            reverse=True,
        )
        selected = ranked[0] if ranked else material_paths[index % len(material_paths)]
        if score_material(sentence, content_tokens, selected, material_tags) <= 0:
            selected = material_paths[index % len(material_paths)]
        used.add(selected)
        item["匹配素材"] = selected.name
        item["匹配原因"] = f"根据素材标签「{material_label(selected, material_tags)}」与文案关键词进行匹配。"
    return storyboard
