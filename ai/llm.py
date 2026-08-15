"""Cursor SDK adapter — all in-product LLM calls go through here."""

from django.conf import settings

from ai.json_utils import parse_json_from_text


class LLMNotConfiguredError(Exception):
    """CURSOR_API_KEY missing or cursor-sdk unavailable."""


class LLMError(Exception):
    """Cursor agent call failed."""


def is_llm_configured() -> bool:
    return bool(settings.CURSOR_API_KEY)


def complete(prompt: str) -> str:
    if not is_llm_configured():
        raise LLMNotConfiguredError('CURSOR_API_KEY is not set')

    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError as exc:
        raise LLMNotConfiguredError('cursor-sdk is not installed') from exc

    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=settings.CURSOR_API_KEY,
                model='composer-2.5',
                local=LocalAgentOptions(cwd=str(settings.BASE_DIR)),
            ),
        )
    except Exception as exc:
        raise LLMError(str(exc)) from exc

    if result.status != 'completed' or not result.result:
        raise LLMError(f'Agent did not complete: {result.status}')

    return result.result.strip()


def complete_json(prompt: str) -> dict | list:
    raw = complete(prompt)
    return parse_json_from_text(raw)
