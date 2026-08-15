"""Groq Whisper — speech-to-text is not an LLM call."""

from pathlib import Path

from django.conf import settings

from ai.llm import LLMNotConfiguredError, groq_client, is_llm_configured

STT_TIMEOUT_SECONDS = 60.0
MIN_SPEECH_LETTERS = 8


def looks_like_speech(transcript: str) -> bool:
    letters = sum(1 for char in transcript if char.isalpha())
    return letters >= MIN_SPEECH_LETTERS


def _read_audio_bytes(audio_file) -> tuple[bytes, str, str]:
    name = getattr(audio_file, 'name', '') or 'audio.webm'
    filename = Path(name).name or 'audio.webm'
    content_type = (
        getattr(audio_file, 'content_type', None)
        or getattr(getattr(audio_file, 'file', None), 'content_type', None)
        or 'audio/webm'
    )

    if hasattr(audio_file, 'open'):
        audio_file.open('rb')
        try:
            data = audio_file.read()
        finally:
            audio_file.close()
    else:
        audio_file.seek(0)
        data = audio_file.read()
        try:
            audio_file.seek(0)
        except Exception:
            pass

    return data, filename, content_type


def transcribe_audio(audio_file) -> str:
    """Return transcript text, or empty string on any failure."""
    if not audio_file or not is_llm_configured():
        return ''

    try:
        data, filename, content_type = _read_audio_bytes(audio_file)
    except Exception:
        return ''

    if not data:
        return ''

    try:
        client = groq_client(timeout=STT_TIMEOUT_SECONDS)
        result = client.audio.transcriptions.create(
            model=settings.GROQ_STT_MODEL,
            file=(filename, data, content_type),
            language='ar',
        )
    except (LLMNotConfiguredError, Exception):
        return ''

    return (getattr(result, 'text', None) or '').strip()
