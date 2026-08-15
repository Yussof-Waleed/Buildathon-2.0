"""Localized field helpers for bilingual catalog and order snapshots."""

from django.utils.translation import get_language


def localized_field(obj, field: str) -> str:
    """
    Return obj.{field}_ar or obj.{field}_en based on active language.
    Falls back to the other language if the preferred side is blank.
    """
    lang = (get_language() or 'ar').split('-')[0]
    primary = f'{field}_ar' if lang == 'ar' else f'{field}_en'
    fallback = f'{field}_en' if lang == 'ar' else f'{field}_ar'
    value = getattr(obj, primary, '') or ''
    if value:
        return value
    return getattr(obj, fallback, '') or ''
