import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pywa import WhatsApp
from pywa import utils as wa_utils

from jobs.whatsapp.client import get_whatsapp_client

logger = logging.getLogger(__name__)


def _to_http_response(result) -> HttpResponse:
    if isinstance(result, HttpResponse):
        return result
    if isinstance(result, tuple) and len(result) == 2:
        body, status = result
        return HttpResponse(body, status=status, content_type='text/plain')
    return HttpResponse(str(result), content_type='text/plain')


def _verification_client() -> WhatsApp:
    """Minimal client for Meta's GET webhook challenge (verify token only)."""
    return WhatsApp(
        phone_id=settings.WHATSAPP_PHONE_ID or '0',
        token=settings.WHATSAPP_TOKEN or 'unused',
        server=None,
        verify_token=settings.WHATSAPP_VERIFY_TOKEN,
    )


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def whatsapp_webhook(request: HttpRequest) -> HttpResponse:
    if request.method == 'GET':
        verify_token = request.GET.get(wa_utils.HUB_VT)
        challenge = request.GET.get(wa_utils.HUB_CH)
        mode = request.GET.get('hub.mode')

        wa = _verification_client()
        body, status = wa.webhook_challenge_handler(vt=verify_token, ch=challenge)

        if status != 200:
            logger.warning(
                'WhatsApp webhook verification failed (status=%s mode=%s token_match=%s)',
                status,
                mode,
                verify_token == settings.WHATSAPP_VERIFY_TOKEN,
            )
            return HttpResponse(
                body or 'Forbidden',
                status=status,
                content_type='text/plain',
            )

        logger.info('WhatsApp webhook verification succeeded')
        return HttpResponse(body, status=status, content_type='text/plain')

    if not settings.WHATSAPP_PHONE_ID or not settings.WHATSAPP_TOKEN:
        return HttpResponse(
            'WhatsApp is not configured. Set WHATSAPP_PHONE_ID and WHATSAPP_TOKEN in .env',
            status=503,
            content_type='text/plain',
        )

    wa = get_whatsapp_client()
    validation_error = wa.webhook_update_validator(
        update=request.body,
        hmac_header=request.headers.get(wa_utils.HUB_SIG),
    )
    if validation_error:
        logger.warning('Rejected WhatsApp webhook update')
        return _to_http_response(validation_error)

    response, status = wa.webhook_update_handler(update=request.body)
    return _to_http_response((response, status))
