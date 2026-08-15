import logging

from django.conf import settings
from pywa.errors import ExpiredAccessToken, WhatsAppError

from jobs.models import Message, Order
from jobs.whatsapp.client import get_whatsapp_client
from jobs.whatsapp.phone import wa_id_from_e164

logger = logging.getLogger(__name__)


def is_whatsapp_configured() -> bool:
    return bool(settings.WHATSAPP_PHONE_ID and settings.WHATSAPP_TOKEN)


def customer_uses_whatsapp(customer) -> bool:
    return Message.objects.filter(
        conversation__customer=customer,
        channel=Message.Channel.WHATSAPP,
    ).exists()


def notify_order_whatsapp(order: Order, text: str) -> bool:
    """Send text to the customer on WhatsApp if they already used that channel."""
    text = (text or '').strip()
    if not text or not is_whatsapp_configured():
        return False
    if not customer_uses_whatsapp(order.customer):
        return False

    try:
        wa_id = wa_id_from_e164(order.customer.phone)
    except ValueError:
        logger.warning('Cannot notify order %s — invalid phone', order.pk)
        return False

    try:
        wa = get_whatsapp_client()
        wa.send_message(to=wa_id, text=text)
    except ExpiredAccessToken:
        logger.exception(
            'WhatsApp token expired — generate a new permanent System User token '
            'in Meta Business Settings, update WHATSAPP_TOKEN, then restart.'
        )
        return False
    except WhatsAppError:
        logger.exception('Failed to send WhatsApp notification for order %s', order.pk)
        return False
    except RuntimeError:
        logger.exception('WhatsApp client is not configured')
        return False

    logger.info('Sent WhatsApp notification for order %s', order.pk)
    return True
