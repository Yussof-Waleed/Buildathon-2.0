from django.conf import settings
from pywa import WhatsApp

_wa_client: WhatsApp | None = None


def get_whatsapp_client() -> WhatsApp:
    """Return the shared PyWa client (lazy singleton)."""
    global _wa_client
    if _wa_client is not None:
        return _wa_client

    if not settings.WHATSAPP_PHONE_ID or not settings.WHATSAPP_TOKEN:
        raise RuntimeError(
            'WhatsApp is not configured. Set WHATSAPP_PHONE_ID and WHATSAPP_TOKEN in .env'
        )

    _wa_client = WhatsApp(
        phone_id=settings.WHATSAPP_PHONE_ID,
        token=settings.WHATSAPP_TOKEN,
        server=None,
        verify_token=settings.WHATSAPP_VERIFY_TOKEN,
        app_id=settings.WHATSAPP_APP_ID or None,
        app_secret=settings.WHATSAPP_APP_SECRET or None,
        validate_updates=bool(settings.WHATSAPP_APP_SECRET),
    )
    return _wa_client
