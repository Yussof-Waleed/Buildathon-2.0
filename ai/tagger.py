"""Assign label IDs and one suggested diagnostic to new orders."""

from dataclasses import dataclass
import re
from typing import Any

from catalog.models import Diagnostic, Label
from ai.llm import LLMError, LLMNotConfiguredError, complete_json


@dataclass
class TaggerResult:
    label_ids: list[int]
    diagnostic_id: int | None = None


# Customer phrasing that should still hit catalog titles.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    'صوت': ('ضوضاء', 'noise', 'سير', 'belt'),
    'ضوضاء': ('صوت', 'noise', 'سير', 'belt'),
    'noise': ('ضوضاء', 'صوت', 'belt', 'سير'),
    'سير': ('belt', 'ضوضاء', 'noise'),
    'belt': ('سير', 'ضوضاء', 'noise'),
    'فرامل': ('brakes', 'تيل', 'brake', 'pads'),
    'brakes': ('فرامل', 'تيل', 'pads'),
    'brake': ('فرامل', 'تيل', 'pads'),
    'تيل': ('فرامل', 'brakes', 'pads'),
    'pads': ('تيل', 'فرامل', 'brakes'),
    'زيت': ('oil',),
    'oil': ('زيت',),
    'فلتر': ('filter', 'زيت', 'oil'),
    'بطارية': ('battery',),
    'battery': ('بطارية',),
    'تكييف': ('ac', 'فريون', 'air'),
    'ac': ('تكييف', 'فريون'),
    'فريون': ('تكييف', 'ac'),
    'كهربا': ('electrical', 'كهرباء'),
    'كهرباء': ('electrical', 'كهربا'),
    'electrical': ('كهرباء', 'كهربا'),
    'حرارة': ('overheating', 'coolant', 'ماء'),
    'overheating': ('حرارة', 'coolant'),
    'coolant': ('حرارة', 'ماء'),
    'عفشة': ('suspension', 'صدمات', 'shocks', 'مساعدين'),
    'suspension': ('عفشة', 'shocks', 'مساعدين'),
    'صدمات': ('suspension', 'عفشة', 'shocks'),
    'shocks': ('عفشة', 'صدمات', 'مساعدين'),
    'مساعدين': ('shocks', 'عفشة', 'suspension'),
    'كلاتش': ('clutch',),
    'clutch': ('كلاتش',),
    'كشف': ('inspection', 'فحص'),
    'inspection': ('كشف', 'فحص'),
    'فحص': ('inspection', 'كشف'),
    'بوجيهات': ('spark', 'plugs'),
    'spark': ('بوجيهات', 'plugs'),
    'plugs': ('بوجيهات', 'spark'),
}

_TOKEN_RE = re.compile(r'[^\W_]+', re.UNICODE)


def _tokens(text: str) -> set[str]:
    found = set()
    for match in _TOKEN_RE.finditer(text.lower()):
        token = match.group(0)
        if len(token) >= 2:
            found.add(token)
    return found


def _expanded_tokens(text: str) -> set[str]:
    tokens = _tokens(text)
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_SYNONYMS.get(token, ()))
    return expanded


def _score(text_tokens: set[str], title_ar: str, title_en: str) -> int:
    return len(text_tokens & _tokens(f'{title_ar} {title_en}'))


def _keyword_fallback(
    order_text: str,
    label_catalog: list[dict],
    diagnostic_catalog: list[dict],
) -> TaggerResult:
    text_tokens = _expanded_tokens(order_text)
    if not text_tokens:
        return TaggerResult(label_ids=[])

    label_ids: list[int] = []
    for item in label_catalog:
        if _score(text_tokens, item['title_ar'], item['title_en']) > 0:
            label_ids.append(item['id'])

    best_id: int | None = None
    best_score = 0
    for item in diagnostic_catalog:
        score = _score(text_tokens, item['title_ar'], item['title_en'])
        if score > best_score:
            best_score = score
            best_id = item['id']

    return TaggerResult(
        label_ids=label_ids,
        diagnostic_id=best_id if best_score > 0 else None,
    )


def _parse_label_ids(data: Any, valid_ids: set[int]) -> list[int]:
    if isinstance(data, list):
        raw_ids = data
    elif isinstance(data, dict):
        raw_ids = data.get('label_ids') or data.get('labels') or []
    else:
        return []

    result: list[int] = []
    for item in raw_ids:
        try:
            lid = int(item)
        except (TypeError, ValueError):
            continue
        if lid in valid_ids and lid not in result:
            result.append(lid)
    return result


def _parse_diagnostic_id(data: Any, valid_ids: set[int]) -> int | None:
    if not isinstance(data, dict):
        return None
    raw = data.get('diagnostic_id')
    if raw is None or raw == '':
        return None
    try:
        diagnostic_id = int(raw)
    except (TypeError, ValueError):
        return None
    if diagnostic_id in valid_ids:
        return diagnostic_id
    return None


def suggest(
    order_text: str,
    label_catalog: list[dict],
    diagnostic_catalog: list[dict],
) -> TaggerResult:
    """
    label_catalog: list of {id, title_ar, title_en}
    diagnostic_catalog: list of {id, title_ar, title_en, price}
    """
    fallback = _keyword_fallback(order_text, label_catalog, diagnostic_catalog)
    if not label_catalog and not diagnostic_catalog:
        return TaggerResult(label_ids=[])

    labels_block = '\n'.join(
        f'- id={item["id"]}, ar={item["title_ar"]}, en={item["title_en"]}'
        for item in label_catalog
    ) or '(none)'
    diagnostics_block = '\n'.join(
        f'- id={item["id"]}, ar={item["title_ar"]}, en={item["title_en"]}, '
        f'price={item.get("price")} EGP'
        for item in diagnostic_catalog
    ) or '(none)'

    prompt = f"""You tag car repair intake for a Cairo neighbourhood garage (Warsha).

Available labels (use only these ids, multi-label):
{labels_block}

Available diagnostics (pick at most ONE best matching job template, or null):
{diagnostics_block}

Customer intake message:
{order_text}

Return ONLY valid JSON:
{{"label_ids": [1, 2], "diagnostic_id": 5}}

Rules:
- Pick every label that fits. Empty array if none match.
- diagnostic_id must be one of the ids above, or null if nothing fits well.
- Prefer the single most specific diagnostic (not a generic inspection unless the customer asked for a check).
"""

    try:
        data = complete_json(prompt)
    except (LLMNotConfiguredError, LLMError, ValueError, TypeError):
        return fallback

    valid_label_ids = {item['id'] for item in label_catalog}
    valid_diagnostic_ids = {item['id'] for item in diagnostic_catalog}
    label_ids = _parse_label_ids(data, valid_label_ids)
    diagnostic_id = _parse_diagnostic_id(data, valid_diagnostic_ids)

    if not label_ids and diagnostic_id is None:
        return fallback
    if diagnostic_id is None:
        diagnostic_id = fallback.diagnostic_id
    return TaggerResult(label_ids=label_ids, diagnostic_id=diagnostic_id)


def suggest_from_db(order_text: str) -> TaggerResult:
    label_catalog = list(Label.objects.values('id', 'title_ar', 'title_en'))
    diagnostic_catalog = list(
        Diagnostic.objects.values('id', 'title_ar', 'title_en', 'price'),
    )
    return suggest(order_text, label_catalog, diagnostic_catalog)


def suggest_labels(order_text: str, label_catalog: list[dict]) -> list[int]:
    """Back-compat: label ids only."""
    return suggest(order_text, label_catalog, []).label_ids


def suggest_labels_from_db(order_text: str) -> list[int]:
    """Back-compat: label ids only."""
    return suggest_from_db(order_text).label_ids
