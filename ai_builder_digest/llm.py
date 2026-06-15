from __future__ import annotations

import json
import os
import urllib.request

from .models import DigestItem


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def llm_enrich_items(items: list[DigestItem], max_items: int = 20) -> int:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return 0
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    updated = 0
    for item in items[:max_items]:
        if llm_enrich_item(item, api_key, model):
            updated += 1
    return updated


def llm_translate_items(items: list[DigestItem], max_items: int = 80, chunk_size: int = 20) -> int:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return 0
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    translated = 0
    selected = items[:max_items]
    for start in range(0, len(selected), chunk_size):
        translated += llm_translate_chunk(selected[start : start + chunk_size], start, api_key, model)
    return translated


def llm_translate_chunk(items: list[DigestItem], offset: int, api_key: str, model: str) -> int:
    if not items:
        return 0
    payload_items = []
    for index, item in enumerate(items):
        payload_items.append(
            {
                "id": offset + index,
                "source": item.source,
                "category": item.category,
                "title": item.title,
                "chinese_title": item.chinese_title,
                "brief": item.brief,
                "importance": item.importance,
                "reason": item.reason,
            }
        )
    payload = {
        "model": model,
        "input": build_translation_prompt(payload_items),
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return 0

    content = extract_response_text(data)
    if not content:
        return 0
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return 0
    if not isinstance(parsed, list):
        return 0

    by_id = {entry.get("id"): entry for entry in parsed if isinstance(entry, dict)}
    updated = 0
    for index, item in enumerate(items):
        entry = by_id.get(offset + index)
        if not isinstance(entry, dict):
            continue
        item.title_en = str(entry.get("title_en", item.title_en))[:260]
        item.brief_en = str(entry.get("brief_en", item.brief_en))[:600]
        item.importance_en = str(entry.get("importance_en", item.importance_en))[:500]
        item.reason_en = str(entry.get("reason_en", item.reason_en))[:500]
        item.title_no = str(entry.get("title_no", item.title_no))[:260]
        item.brief_no = str(entry.get("brief_no", item.brief_no))[:600]
        item.importance_no = str(entry.get("importance_no", item.importance_no))[:500]
        item.reason_no = str(entry.get("reason_no", item.reason_no))[:500]
        updated += 1
    return updated


def build_translation_prompt(items: list[dict[str, object]]) -> str:
    return f"""Translate these news digest cards for a static multilingual page.
Return JSON only: an array with one object per input id.
Required keys: id, title_en, brief_en, importance_en, reason_en, title_no, brief_no, importance_no, reason_no.

Rules:
- English should be concise, neutral, and news-digest style.
- Norwegian must be Bokmål, concise, and natural for a Norwegian reader.
- Preserve names, organizations, numbers, dates, NATO, EØS, NRK, VG, and source names.
- Do not add facts that are not present.
- If a field is empty, translate from the closest available title/brief/reason.
- For Norwegian-source titles, title_no may keep the original Norwegian title when it is already natural.

Items:
{json.dumps(items, ensure_ascii=False)}
"""


def llm_enrich_item(item: DigestItem, api_key: str, model: str) -> bool:
    prompt = build_prompt(item)
    payload = {
        "model": model,
        "input": prompt,
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False

    content = extract_response_text(data)
    if not content:
        return False
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return False

    item.brief = str(parsed.get("brief", item.brief))[:500]
    item.importance = str(parsed.get("importance", item.importance))[:500]
    item.credibility = str(parsed.get("credibility", item.credibility))[:500]
    item.claim_check = str(parsed.get("claim_check", item.claim_check))[:500]
    item.judge = str(parsed.get("judge", item.judge))[:40]
    item.judge_reason = str(parsed.get("judge_reason", item.judge_reason))[:500]
    return True


def extract_response_text(data: dict[str, object]) -> str:
    output = data.get("output")
    if not isinstance(output, list):
        return ""
    for block in output:
        if not isinstance(block, dict):
            continue
        content = block.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                return str(part["text"])
    return ""


def build_prompt(item: DigestItem) -> str:
    source_text = item.article_text or item.summary or item.title
    return f"""You are an analyst preparing a concise Chinese intelligence digest.
Return JSON only with these keys: brief, importance, credibility, claim_check, judge, judge_reason.
judge must be "keep" or "review".

Source: {item.source}
Category: {item.category}
Title: {item.title}
Current rule reason: {item.reason}
Text:
{source_text[:3000]}
"""
