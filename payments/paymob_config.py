"""Paymob configuration readiness checks."""

from django.conf import settings


def _looks_like_api_key(value: str) -> bool:
    """Paymob API keys are long base64 JWT-style strings, not Secret keys."""
    if not value:
        return False
    if value.startswith('egy_sk_') or value.startswith('sk_'):
        return False
    return len(value) > 80 or value.startswith('ZXlK')


def _looks_like_public_key(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return 'pk' in lowered or value.startswith('egy_pk_')


def get_paymob_readiness() -> dict:
    missing = []
    warnings = []

    secret = settings.PAYMOB_SECRET_KEY or ''
    public = settings.PAYMOB_PUBLIC_KEY or ''
    hmac_secret = settings.PAYMOB_HMAC_SECRET or ''
    integration_id = settings.PAYMOB_INTEGRATION_ID_CARD or ''

    if not secret:
        missing.append('PAYMOB_SECRET_KEY')
    elif _looks_like_api_key(secret):
        warnings.append(
            'PAYMOB_SECRET_KEY looks like API key — paste Secret key (Test) '
            '(egy_sk_test_…) from Paymob portal, not API key'
        )

    if not public:
        missing.append('PAYMOB_PUBLIC_KEY')
    elif not _looks_like_public_key(public):
        warnings.append(
            'PAYMOB_PUBLIC_KEY format unexpected — use Public key (Test) '
            '(egy_pk_test_…) from Paymob portal'
        )

    if not hmac_secret:
        missing.append('PAYMOB_HMAC_SECRET')

    if not integration_id:
        missing.append('PAYMOB_INTEGRATION_ID_CARD')

    ready = len(missing) == 0 and not any(
        'looks like API key' in w for w in warnings
    )

    return {
        'ready': ready,
        'missing': missing,
        'warnings': warnings,
    }
