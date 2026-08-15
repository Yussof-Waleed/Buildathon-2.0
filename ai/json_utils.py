import json
import re


def parse_json_from_text(text: str):
    stripped = text.strip()
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', stripped)
    if fence:
        stripped = fence.group(1).strip()
    return json.loads(stripped)

