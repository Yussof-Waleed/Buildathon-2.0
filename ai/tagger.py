"""Assign label IDs to new orders from catalog."""

from catalog.models import Label
from ai.llm import LLMError, LLMNotConfiguredError, complete_json


def suggest_labels(order_text: str, label_catalog: list[dict]) -> list[int]:
    """
    label_catalog: list of {id, title_ar, title_en}
    Returns validated label ids.
    """
    if not label_catalog:
        return []

    labels_block = '\n'.join(
        f'- id={item["id"]}, ar={item["title_ar"]}, en={item["title_en"]}'
        for item in label_catalog
    )

    prompt = f"""You tag car repair intake messages for a Cairo garage.

Available labels (use only these ids):
{labels_block}

Customer intake message:
{order_text}

Return ONLY valid JSON:
{{"label_ids": [1, 2]}}

Pick all labels that fit (multi-label). Use empty array if none match."""

    try:
        data = complete_json(prompt)
    except (LLMNotConfiguredError, LLMError, ValueError, TypeError):
        return []

    if isinstance(data, list):
        raw_ids = data
    elif isinstance(data, dict):
        raw_ids = data.get('label_ids') or data.get('labels') or []
    else:
        return []

    valid_ids = {item['id'] for item in label_catalog}
    result = []
    for item in raw_ids:
        try:
            lid = int(item)
        except (TypeError, ValueError):
            continue
        if lid in valid_ids and lid not in result:
            result.append(lid)
    return result


def suggest_labels_from_db(order_text: str) -> list[int]:
    catalog = list(Label.objects.values('id', 'title_ar', 'title_en'))
    return suggest_labels(order_text, catalog)
