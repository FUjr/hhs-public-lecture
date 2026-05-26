from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LESSON_DIR = ROOT / "lesson_plan"
OUTPUT_DIR = ROOT / "public" / "generated-lessons"
GENERATOR_VERSION = "2"
SOURCE_HASH_KEY = "sourceHash"
GENERATED_BY_KEY = "generatedBy"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate static lesson JSON from lesson_plan markdown files.")
    parser.add_argument("--force", action="store_true", help="Regenerate even when source hash is unchanged.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lessons: list[dict] = []
    active_ids: set[str] = set()

    lesson_files = sorted(LESSON_DIR.glob("*.md"))
    if not lesson_files:
        raise SystemExit("No lesson_plan/*.md files found.")

    for path in lesson_files:
        markdown = path.read_text(encoding="utf-8")
        source_hash = markdown_hash(markdown)
        lesson_id = slugify(path.stem)
        output_path = OUTPUT_DIR / f"{lesson_id}.json"
        cached = None if args.force else load_cached_lesson(output_path, source_hash)
        if cached:
            lesson = cached
        else:
            fallback = build_fallback_lesson(path, markdown)
            ai_lesson = generate_with_ai(markdown, fallback)
            lesson = merge_lesson(fallback, ai_lesson)
            lesson["id"] = lesson_id
            lesson["lessonPlanSource"] = str(path.relative_to(ROOT))
            lesson[SOURCE_HASH_KEY] = source_hash
            lesson[GENERATED_BY_KEY] = "ai" if ai_lesson else "fallback"
            write_json(output_path, lesson)
        active_ids.add(lesson_id)
        lessons.append({
            "id": lesson_id,
            "title": lesson.get("title", lesson_id),
            "subtitle": lesson.get("subtitle", ""),
        })

    for stale in OUTPUT_DIR.glob("*.json"):
        if stale.name == "index.json":
            continue
        if stale.stem not in active_ids:
            stale.unlink()

    write_json(OUTPUT_DIR / "index.json", {"lessons": lessons})
    print(f"Generated {len(lessons)} lesson(s) into {OUTPUT_DIR.relative_to(ROOT)}")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def markdown_hash(markdown: str) -> str:
    payload = f"{GENERATOR_VERSION}\n{markdown}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_cached_lesson(path: Path, source_hash: str) -> dict | None:
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if parsed.get(SOURCE_HASH_KEY) == source_hash:
        return parsed
    return None


def build_fallback_lesson(path: Path, markdown: str) -> dict:
    title = extract_title(markdown) or path.stem
    goals = extract_numbered_items(extract_section(markdown, ["学习目标", "教学目标"]))
    key_points = first_non_empty_line(extract_section(markdown, ["学习重点", "重点"]))
    difficult_points = first_non_empty_line(extract_section(markdown, ["学习难点", "难点"]))
    presets = extract_presets(markdown)
    flower_cards = extract_flower_cards(markdown)
    ai_prompt = extract_ai_prompt(markdown) or "请结合课文内容和自己的经历，说说你对本课核心观点的理解。"
    core = extract_core_statement(markdown, ai_prompt)

    return {
        "id": slugify(path.stem),
        "title": title,
        "subtitle": "课堂对话 AI",
        "questionPrompt": "围绕课文内容、写作手法和现实思考提出一个有价值的问题。",
        "aiStudentPrompt": ai_prompt,
        "askPanelTitle": "看课文，也看自己",
        "askPanelDescription": "学生自由提问，AI 围绕课文内容、写作手法和现实思考作答。",
        "questionPlaceholder": "输入学生问题",
        "emptyAskMark": first_cjk_char(title) or "问",
        "emptyReflectMark": "问",
        "coreStatement": core,
        "goals": goals,
        "keyPoints": key_points,
        "difficultPoints": difficult_points,
        "stages": extract_stages(markdown),
        "questionCues": [
            "可以从“为什么这样安排内容”发问。",
            "可以从“作者真正想表达什么”发问。",
            "可以从“课文和现实生活有什么关系”发问。",
        ],
        "flowerCards": flower_cards,
        "thinkingSteps": [
            {"title": "2 分钟", "description": "独立写关键词"},
            {"title": "2 分钟", "description": "小组交流观点"},
            {"title": "3 分钟", "description": "全班代表分享"},
        ],
        "reflectionHints": [
            {"title": "先表明立场", "description": "说明你更认同哪一种观点，或者是否想辩证看待。"},
            {"title": "再联系经历", "description": "联系学习、同学相处、网络环境或身边见闻。"},
            {"title": "最后回到课文", "description": "想一想你的观点怎样理解课文中的核心语句。"},
        ],
        "presets": presets,
        "summaryTemplate": extract_summary(markdown),
        "homeworkTemplate": extract_homework(markdown),
    }


def generate_with_ai(markdown: str, fallback: dict) -> dict | None:
    endpoint = os.getenv("V2_LESSON_AI_ENDPOINT", "").strip()
    api_key = os.getenv("V2_LESSON_AI_API_KEY", "").strip()
    model = os.getenv("V2_LESSON_AI_MODEL", "gpt-4.1-mini").strip()
    if not endpoint:
        return None

    prompt = (
        "你是语文公开课模板生成器。请根据 Markdown 教案生成课堂互动模板 JSON。"
        "只能输出 JSON 对象，不要 Markdown。字段必须包含：subtitle, questionPrompt, aiStudentPrompt, "
        "askPanelTitle, askPanelDescription, questionPlaceholder, questionCues, flowerCards, thinkingSteps, "
        "reflectionHints, presets, summaryTemplate, homeworkTemplate。flowerCards 每项包含 mark, title, description，"
        "必须根据教案动态生成，不要写死固定花名；没有适合意象时返回空数组。presets 每项包含 "
        "title, category, question, keywords, answer。回答要适合七年级课堂，中文自然简洁。\n\n"
        f"已有默认 JSON：{json.dumps(fallback, ensure_ascii=False)}\n\nMarkdown 教案：\n{markdown}"
    )

    url, mode = normalize_endpoint(endpoint)
    request = urllib.request.Request(
        url,
        data=json.dumps(build_ai_payload(mode, model, prompt), ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
        text = strip_code_fence(extract_ai_text(json.loads(raw)))
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.HTTPError, urllib.error.URLError) as exc:
        print(f"AI lesson generation failed: {exc}", file=sys.stderr)
        return None


def merge_lesson(fallback: dict, ai_lesson: dict | None) -> dict:
    if not ai_lesson:
        return fallback
    merged = dict(fallback)
    for key in [
        "subtitle",
        "questionPrompt",
        "aiStudentPrompt",
        "askPanelTitle",
        "askPanelDescription",
        "questionPlaceholder",
        "summaryTemplate",
        "homeworkTemplate",
        "coreStatement",
    ]:
        value = ai_lesson.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    for key in ["questionCues", "flowerCards", "thinkingSteps", "reflectionHints", "presets", "goals", "stages"]:
        value = ai_lesson.get(key)
        if isinstance(value, list) and value:
            merged[key] = value
    return merged


def extract_title(markdown: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, flags=re.MULTILINE)
    return clean_markdown(match.group(1)) if match else ""


def extract_section(markdown: str, headings: list[str]) -> str:
    for heading in headings:
        pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
        match = re.search(pattern, markdown, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def extract_raw_heading(markdown: str, heading: str) -> str:
    pattern = rf"^#+\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^#+\s+|\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def extract_numbered_items(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        cleaned = clean_markdown(line)
        match = re.match(r"^\d+[、.]\s*(.+)$", cleaned)
        if match:
            items.append(match.group(1).strip())
    return items


def extract_presets(markdown: str) -> list[dict]:
    section = extract_raw_heading(markdown, "预设问题") or extract_bold_block(markdown, "预设问题")
    if not section:
        return []
    chunks = re.split(r"^\s*-\s+", section, flags=re.MULTILINE)
    presets: list[dict] = []
    for chunk in chunks:
        lines = [clean_markdown(line) for line in chunk.splitlines() if clean_markdown(line)]
        if len(lines) < 2:
            continue
        question = lines[0].rstrip("：:")
        answer = "".join(lines[1:])
        presets.append({
            "title": question[:18],
            "category": "预设问题",
            "question": question,
            "keywords": keyword_candidates(question + answer),
            "answer": answer,
        })
    return presets


def extract_flower_cards(markdown: str) -> list[dict]:
    cards: list[dict] = []
    seen: set[str] = set()
    pattern = r"^\s*([^\s—-]{1,8})\s*(?:—|-){2}\s*([^—\-\n]+?)\s*(?:—|-){2}\s*([^\n]+)\s*$"
    for match in re.finditer(pattern, markdown, flags=re.MULTILINE):
        mark = clean_markdown(match.group(1))
        title = clean_markdown(match.group(2))
        description = clean_markdown(match.group(3))
        if mark and mark not in seen:
            cards.append({"mark": mark[:3], "title": f"{mark}：{title}", "description": description})
            seen.add(mark)
    return cards


def extract_ai_prompt(markdown: str) -> str:
    match = re.search(r"\*\*AI提问\*\*[:：]\s*(.+)", markdown)
    if match:
        return clean_markdown(match.group(1))
    match = re.search(r"AI提问[:：]\s*(.+)", markdown)
    return clean_markdown(match.group(1)) if match else ""


def extract_core_statement(markdown: str, ai_prompt: str) -> str:
    for candidate in ["出淤泥而不染", "核心主旨", "中心思想"]:
        if candidate in markdown:
            return candidate
    return first_sentence(ai_prompt)


def extract_stages(markdown: str) -> list[dict]:
    section = extract_raw_heading(markdown, "教学设计")
    if not section:
        section = markdown
    stages = []
    for match in re.finditer(r"^###\s+(.+?)\s*$", section, flags=re.MULTILINE):
        title = clean_markdown(match.group(1))
        if title:
            stages.append({"title": title, "description": "按教案推进课堂活动。"})
    return stages or [
        {"title": "课前过渡", "description": "回顾预习任务，进入课堂主题。"},
        {"title": "文本理解", "description": "梳理课文内容与关键概念。"},
        {"title": "对话 AI", "description": "通过问答推进探究和表达。"},
    ]


def extract_summary(markdown: str) -> str:
    match = re.search(r"\*\*教师小结\*\*[:：]\s*(.+)", markdown)
    if match:
        return clean_markdown(match.group(1))
    section = extract_raw_heading(markdown, "教师点评与升华")
    return clean_markdown(section) if section else "请结合本节课的目标、重点和课堂生成内容进行总结。"


def extract_homework(markdown: str) -> str:
    section = extract_section(markdown, ["课后练习任务"])
    if section:
        section = section.split("\n---", 1)[0]
        return clean_markdown(section)
    section = extract_raw_heading(markdown, "课后总结 仿写提升")
    return clean_markdown(section) if section else "请完成本课相关练习，并整理课堂收获。"


def extract_bold_block(markdown: str, label: str) -> str:
    pattern = rf"^\*\*{re.escape(label)}\*\*[:：]?\s*$([\s\S]*?)(?=^\*\*.+?\*\*|^####?\s+|^##\s+|\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = clean_markdown(line)
        if cleaned:
            return cleaned
    return ""


def first_sentence(text: str) -> str:
    cleaned = clean_markdown(text)
    match = re.search(r"(.+?[。！？!?])", cleaned)
    return match.group(1) if match else cleaned


def clean_markdown(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-")
    if cleaned:
        return cleaned
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
    return encoded[:18]


def first_cjk_char(text: str) -> str:
    match = re.search(r"[\u4e00-\u9fff]", text)
    return match.group(0) if match else ""


def keyword_candidates(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"[，,、？?：:\s]+", text) if len(part.strip()) >= 2]
    return parts[:8]


def normalize_endpoint(endpoint: str) -> tuple[str, str]:
    cleaned = endpoint.strip().rstrip("/")
    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    lower = cleaned.lower()
    if lower.endswith("/responses"):
        return cleaned, "responses"
    if lower.endswith("/chat/completions") or lower.endswith("/completions"):
        return cleaned, "chat_completions"
    if path in ("", "/", "/v1", "/v1beta", "/v1beta1"):
        if "api.openai.com" in host:
            return f"{cleaned}/responses", "responses"
        return f"{cleaned}/chat/completions", "chat_completions"
    return cleaned, "responses" if "api.openai.com" in host else "chat_completions"


def build_ai_payload(mode: str, model: str, prompt: str) -> dict:
    if mode == "chat_completions":
        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
    return {"model": model, "input": prompt}


def extract_ai_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    output = payload.get("output")
    if isinstance(output, list):
        collected = []
        for item in output:
            for block in item.get("content", []) if isinstance(item, dict) else []:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    collected.append(block["text"])
        if collected:
            return "\n".join(collected)
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        content = choices[0].get("message", {}).get("content") if isinstance(choices[0], dict) else None
        if isinstance(content, str):
            return content
    return ""


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


if __name__ == "__main__":
    main()
