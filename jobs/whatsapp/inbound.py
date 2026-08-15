import logging
import threading
import re

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import close_old_connections, IntegrityError
from django.utils.translation import gettext as _
from pywa import types as wa_types
from pywa.errors import ExpiredAccessToken, WhatsAppError

from accounts.models import Customer
from jobs.models import Message
from jobs.services import ProcessChatResult, process_chat_message
from jobs.whatsapp.client import get_whatsapp_client
from jobs.whatsapp.events import notify_progress
from jobs.whatsapp.phone import e164_from_wa_id

logger = logging.getLogger(__name__)


def _customer_body(msg: wa_types.Message) -> str:
    text = (msg.text or '').strip()
    if text:
        return text
    if msg.voice or msg.audio:
        return ''
    if msg.image:
        return _('صورة من واتساب')
    if msg.video:
        return _('فيديو من واتساب')
    return _('رسالة من واتساب')


def _download_audio(msg: wa_types.Message) -> ContentFile | None:
    if not (msg.voice or msg.audio):
        return None

    data = msg.get_media_bytes()
    safe_id = re.sub(r'[^A-Za-z0-9_-]+', '_', msg.id)[:80]
    return ContentFile(data, name=f'{safe_id}.ogg')


def _reply_text(result: ProcessChatResult) -> str:
    if result.route == 'irrelevant':
        return _('أهلاً! احكيلنا عن مشكلة العربية لو محتاج صيانة.')
    if result.order_id and result.route == 'existing_order':
        return _('اتضافت رسالتك على الطلب رقم %(id)s.') % {'id': result.order_id}
    if result.order_id:
        return _('وصلنا رسالتك — كريم هيراجع الطلب رقم %(id)s.') % {
            'id': result.order_id,
        }
    return _('وصلنا رسالتك.')


def _send_reply(wa_id: str, text: str, conversation) -> None:
    wa = get_whatsapp_client()
    try:
        wa.send_message(to=wa_id, text=text)
    except ExpiredAccessToken:
        logger.exception(
            'WhatsApp token expired — generate a new permanent System User token '
            'in Meta Business Settings, update WHATSAPP_TOKEN, then restart.'
        )
        return
    except WhatsAppError:
        logger.exception('Failed to send WhatsApp reply to %s', wa_id)
        return

    if conversation is None:
        return
    last = (
        conversation.messages.filter(
            author_type__in=[
                Message.AuthorType.MECHANIC,
                Message.AuthorType.SYSTEM,
            ],
            body=text,
        )
        .order_by('-created_at')
        .first()
    )
    if last:
        return
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=text,
        channel=Message.Channel.WHATSAPP,
    )


def process_inbound_message(msg: wa_types.Message) -> None:
    """Map a WhatsApp message onto the existing Warsha chat flow."""
    if Message.objects.filter(wa_message_id=msg.id).exists():
        logger.info('Skipping duplicate WhatsApp message %s', msg.id)
        return

    phone = e164_from_wa_id(msg.from_user.wa_id)
    customer, _created = Customer.objects.get_or_create(phone=phone)
    audio = _download_audio(msg)
    body = _customer_body(msg)

    try:
        result = process_chat_message(
            customer,
            body,
            audio=audio,
            channel=Message.Channel.WHATSAPP,
            wa_message_id=msg.id,
        )
    except IntegrityError:
        logger.info('Skipping duplicate WhatsApp message %s', msg.id)
        return
    except ValidationError as exc:
        text = ' '.join(exc.messages) if getattr(exc, 'messages', None) else str(exc)
        _send_reply(msg.from_user.wa_id, text, None)
        return

    conversation = None
    stored = Message.objects.filter(wa_message_id=msg.id).select_related(
        'conversation',
    ).first()
    if stored:
        conversation = stored.conversation
        if result.route == 'irrelevant':
            mechanic_reply = (
                conversation.messages.filter(
                    author_type=Message.AuthorType.MECHANIC,
                )
                .exclude(wa_message_id=msg.id)
                .order_by('-created_at')
                .first()
            )
            if mechanic_reply and mechanic_reply.body:
                _send_reply(msg.from_user.wa_id, mechanic_reply.body, conversation)
                return

        order = conversation.order
        if order and result.route in ('existing_order', 'dumb_fallback'):
            notify_progress(order)
            logger.info(
                'Processed WhatsApp message %s for customer %s route=%s order=%s',
                msg.id,
                customer.pk,
                result.route,
                result.order_id,
            )
            return

    _send_reply(msg.from_user.wa_id, _reply_text(result), conversation)
    logger.info(
        'Processed WhatsApp message %s for customer %s route=%s order=%s',
        msg.id,
        customer.pk,
        result.route,
        result.order_id,
    )


def schedule_inbound_processing(msg: wa_types.Message) -> None:
    """Run processing off the webhook thread so Meta gets a fast 200."""

    def _run() -> None:
        close_old_connections()
        try:
            process_inbound_message(msg)
        except Exception:
            logger.exception('WhatsApp inbound processing failed for %s', msg.id)
        finally:
            close_old_connections()

    threading.Thread(target=_run, daemon=True).start()
