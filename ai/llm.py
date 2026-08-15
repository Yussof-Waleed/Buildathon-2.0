"""Groq adapter — all in-product LLM calls go through here."""

from django.conf import settings

from ai.json_utils import parse_json_from_text

GROQ_TIMEOUT_SECONDS = 30.0


class LLMNotConfiguredError(Exception):
    """GROQ_API_KEY missing or groq SDK unavailable."""


class LLMError(Exception):
    """Groq chat call failed."""


def is_llm_configured() -> bool:
    return bool(settings.GROQ_API_KEY)


def groq_client(*, timeout: float = GROQ_TIMEOUT_SECONDS):
    if not is_llm_configured():
        raise LLMNotConfiguredError('GROQ_API_KEY is not set')
    try:
        from groq import Groq
    except ImportError as exc:
        raise LLMNotConfiguredError('groq is not installed') from exc
    return Groq(api_key=settings.GROQ_API_KEY, timeout=timeout)


def complete(prompt: str, *, json_mode: bool = False) -> str:
    client = groq_client()
    kwargs = {
        'model': settings.GROQ_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if json_mode:
        kwargs['response_format'] = {'type': 'json_object'}
    try:
        result = client.chat.completions.create(**kwargs)
    except LLMNotConfiguredError:
        raise
    except Exception as exc:
        raise LLMError(str(exc)) from exc

    choice = result.choices[0] if result.choices else None
    content = (choice.message.content or '').strip() if choice else ''
    if not content:
        raise LLMError('Groq returned an empty completion')
    return content


def complete_json(prompt: str) -> dict | list:
    raw = complete(prompt, json_mode=True)
    return parse_json_from_text(raw)
