"""Order lifecycle helpers — intake and quote snapshot."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import Customer
from catalog.models import Diagnostic
from jobs.models import Conversation, Message, Order, OrderStep
from jobs.whatsapp.events import (
    notify_mechanic_reply,
    notify_quote,
    notify_ready,
    notify_step_done,
    notify_work_started,
)

MAX_AUDIO_BYTES = 10 * 1024 * 1024

OPEN_ORDER_STATUSES = (
    Order.Status.PENDING_REVIEW,
    Order.Status.QUOTED,
    Order.Status.PAID,
    Order.Status.IN_PROGRESS,
    Order.Status.READY_FOR_PICKUP,
)

Route = Literal['new_request', 'existing_order', 'irrelevant', 'dumb_fallback', 'incomplete_intake']


@dataclass
class ProcessChatResult:
    route: Route
    order_id: int | None = None
    redirect: bool = False


def order_chat_is_open(order: Order | None) -> bool:
    return order is None or order.chat_open


def assert_order_chat_open(order: Order | None) -> None:
    if not order_chat_is_open(order):
        raise ValidationError(_('This chat is closed — the order was cancelled.'))


def validate_audio_upload(audio_file) -> None:
    if not audio_file:
        return
    if audio_file.size > MAX_AUDIO_BYTES:
        raise ValidationError('حجم التسجيل كبير — الحد 10 ميجابايت.')
    content_type = (audio_file.content_type or '').lower()
    if content_type and not content_type.startswith('audio/'):
        raise ValidationError('نوع الملف غير مدعوم — استخدم تسجيل صوتي.')


def _get_conversation(order: Order) -> Conversation | None:
    try:
        return order.conversation
    except Conversation.DoesNotExist:
        return None


def _ensure_conversation(order: Order) -> Conversation:
    conversation = _get_conversation(order)
    if conversation:
        return conversation
    return Conversation.objects.create(
        customer=order.customer,
        order=order,
    )


def create_order_from_intake(
    customer: Customer,
    body: str,
    audio=None,
    conversation: Conversation | None = None,
    channel: str = Message.Channel.WEB,
    wa_message_id: str | None = None,
) -> Order:
    """Dumb intake: bind the current conversation to a new pending_review order."""
    if conversation is None:
        conversation = get_or_create_current_conversation(customer)
    assert_order_chat_open(conversation.order)
    if conversation.order_id:
        Message.objects.create(
            conversation=conversation,
            author_type=Message.AuthorType.CUSTOMER,
            body=body.strip(),
            audio=audio,
            channel=channel,
            wa_message_id=wa_message_id,
        )
        return conversation.order

    order = Order.objects.create(
        customer=customer,
        status=Order.Status.PENDING_REVIEW,
    )
    conversation.order = order
    conversation.save(update_fields=['order'])
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.CUSTOMER,
        body=body.strip(),
        audio=audio,
        channel=channel,
        wa_message_id=wa_message_id,
    )
    return order


def snapshot_diagnostic_on_order(
    order: Order,
    diagnostic: Diagnostic,
    kareem_note: str = '',
) -> Order:
    """Copy diagnostic price and steps onto order; set status to quoted."""
    order.diagnostic = diagnostic
    order.quoted_title_ar = diagnostic.title_ar
    order.quoted_title_en = diagnostic.title_en
    order.quoted_price = diagnostic.price
    order.kareem_note = kareem_note
    order.status = Order.Status.QUOTED
    order.save()

    order.steps.all().delete()
    OrderStep.objects.bulk_create([
        OrderStep(
            order=order,
            title_ar=step.title_ar,
            title_en=step.title_en,
            description_ar=step.description_ar,
            description_en=step.description_en,
            expected_minutes=step.expected_minutes,
            sort_order=step.sort_order,
        )
        for step in diagnostic.steps.all()
    ])

    conversation = _ensure_conversation(order)

    steps_lines = [
        f'{step.title_en}|{step.expected_minutes}'
        for step in order.steps.all()
    ]
    quote_lines = [
        '__quote__',
        diagnostic.title_en,
        str(order.quoted_price),
        *steps_lines,
    ]
    if kareem_note:
        quote_lines.append(kareem_note)
    body = '\n'.join(quote_lines)

    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=body,
        channel=Message.Channel.WEB,
    )

    notify_quote(order)
    return order


def start_order_work(order: Order) -> Order:
    """Kareem starts the job after payment — quoted/paid never auto-start."""
    if order.status != Order.Status.PAID:
        return order

    order.status = Order.Status.IN_PROGRESS
    order.save(update_fields=['status', 'updated_at'])

    conversation = _ensure_conversation(order)
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body='__started__',
        channel=Message.Channel.WEB,
    )
    notify_work_started(order)
    return order


def complete_order_step(order: Order, step_id: int) -> Order:
    """Mark one step done; auto ready_for_pickup when all steps complete."""
    if order.status != Order.Status.IN_PROGRESS:
        return order

    step = order.steps.filter(pk=step_id, completed_at__isnull=True).first()
    if not step:
        return order

    now = timezone.now()
    step.completed_at = now
    step.save(update_fields=['completed_at'])

    conversation = _ensure_conversation(order)
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=f'__step__\n{step.title_en}',
        channel=Message.Channel.WEB,
    )

    if not order.steps.filter(completed_at__isnull=True).exists():
        order.status = Order.Status.READY_FOR_PICKUP
        order.save(update_fields=['status', 'updated_at'])
        Message.objects.create(
            conversation=conversation,
            author_type=Message.AuthorType.MECHANIC,
            body='__ready__',
            channel=Message.Channel.WEB,
        )
        notify_ready(order)
    else:
        notify_step_done(order, step.localized_title)

    return order


def mark_ready_for_pickup(order: Order) -> Order:
    """Instant-complete remaining steps and notify customer to collect."""
    if order.status != Order.Status.IN_PROGRESS:
        return order

    now = timezone.now()
    order.steps.filter(completed_at__isnull=True).update(completed_at=now)
    order.status = Order.Status.READY_FOR_PICKUP
    order.save(update_fields=['status', 'updated_at'])

    conversation = _ensure_conversation(order)

    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body='__ready__',
        channel=Message.Channel.WEB,
    )

    notify_ready(order)
    return order


def mark_order_completed(order: Order) -> Order:
    """Terminal state — customer collected the car."""
    if order.status != Order.Status.READY_FOR_PICKUP:
        return order

    order.status = Order.Status.COMPLETED
    order.save(update_fields=['status', 'updated_at'])

    conversation = _ensure_conversation(order)
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body='__completed__',
        channel=Message.Channel.WEB,
    )

    notify_mechanic_reply(
        order,
        _('تم استلام العربية — شكراً لثقتك في ورشة كريم.'),
    )
    return order


def piasters_from_egp(amount: Decimal) -> int:
    return int(amount * 100)


def egp_from_piasters(piasters: int) -> Decimal:
    return Decimal(piasters) / 100


def get_or_create_intake_conversation(customer: Customer) -> Conversation:
    """Always the unbound inbox so a new repair can start while other jobs are open."""
    unbound = Conversation.objects.filter(
        customer=customer,
        order__isnull=True,
    ).order_by('-created_at').first()
    if unbound:
        return unbound
    return Conversation.objects.create(customer=customer, order=None)


def get_or_create_current_conversation(customer: Customer) -> Conversation:
    return get_or_create_intake_conversation(customer)


def _open_orders_queryset(customer: Customer):
    return Order.objects.filter(
        customer=customer,
        status__in=OPEN_ORDER_STATUSES,
    ).order_by('-created_at')


def _order_summary(order: Order) -> str:
    conversation = _get_conversation(order)
    if conversation:
        first = conversation.messages.filter(
            author_type=Message.AuthorType.CUSTOMER,
        ).first()
        if first and first.body:
            return first.body[:120]
        if first and first.audio:
            return 'رسالة صوتية'
    return order.get_status_display()


def _open_orders_for_labeler(customer: Customer) -> list[dict]:
    return [
        {
            'id': order.pk,
            'status': order.status,
            'summary': _order_summary(order),
        }
        for order in _open_orders_queryset(customer)
    ]


def _intake_order_link_body(order_id: int, prefix: str) -> str:
    return f'[order:{order_id}] {prefix}'


def _apply_tagger(order: Order, labeler_text: str) -> None:
    from ai.tagger import suggest_from_db

    result = suggest_from_db(labeler_text)
    if result.label_ids:
        order.labels.set(result.label_ids)
    if result.diagnostic_id:
        order.suggested_diagnostic_id = result.diagnostic_id
        order.save(update_fields=['suggested_diagnostic_id'])


def _bind_conversation_to_new_order(
    conversation: Conversation,
    customer: Customer,
    labeler_text: str,
) -> Order:
    order = Order.objects.create(
        customer=customer,
        status=Order.Status.PENDING_REVIEW,
    )
    conversation.order = order
    conversation.save(update_fields=['order'])
    _apply_tagger(order, labeler_text)
    return order


def _fork_conversation_for_new_order(
    parent: Conversation,
    triggering_message: Message,
    customer: Customer,
    labeler_text: str,
) -> Order:
    order = Order.objects.create(
        customer=customer,
        status=Order.Status.PENDING_REVIEW,
    )
    child = Conversation.objects.create(
        customer=customer,
        order=order,
        parent=parent,
    )
    triggering_message.conversation = child
    triggering_message.save(update_fields=['conversation'])
    Message.objects.create(
        conversation=parent,
        author_type=Message.AuthorType.MECHANIC,
        body=_intake_order_link_body(order.pk, 'تم فتح طلب جديد من المحادثة دي'),
        channel=Message.Channel.WEB,
    )
    _apply_tagger(order, labeler_text)
    return order


def post_mechanic_message(order: Order, body: str, audio=None) -> Message:
    assert_order_chat_open(order)
    conversation = _ensure_conversation(order)
    message = Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=body.strip(),
        audio=audio,
        channel=Message.Channel.WEB,
    )
    text = body.strip()
    if not text and audio:
        text = _('كريم بعت تسجيل صوتي — تقدر تسمعه من صفحة الطلب:') + (
            f'\n{settings.SITE_URL}/orders/{order.pk}/'
        )
    if text:
        notify_mechanic_reply(order, text)
    return message


def _customer_intake_parts(conversation: Conversation) -> tuple[bool, bool]:
    customer_messages = conversation.messages.filter(
        author_type=Message.AuthorType.CUSTOMER,
    )
    has_text = customer_messages.exclude(body='').exists()
    has_audio = any(bool(message.audio) for message in customer_messages)
    return has_text, has_audio


def _intake_incomplete_prompt(has_text: bool, has_audio: bool) -> str | None:
    if has_text and has_audio:
        return None
    if has_text:
        return _('وصلنا وصفك — ابعت كمان تسجيل صوتي لصوت المحرك أو المشكلة.')
    if has_audio:
        return _('وصلنا التسجيل — اكتب كمان وصف للمشكلة في رسالة.')
    return _('ابعت وصف مكتوب وتسجيل صوتي للمشكلة.')


def _labeler_text_for_intake(conversation: Conversation) -> str:
    from ai.labeler import AUDIO_PLACEHOLDER
    from ai.stt import looks_like_speech, transcribe_audio

    texts: list[str] = []
    for message in conversation.messages.filter(
        author_type=Message.AuthorType.CUSTOMER,
    ).order_by('created_at'):
        if message.body.strip():
            texts.append(message.body.strip())
            continue
        if not message.audio:
            continue
        transcript = transcribe_audio(message.audio)
        if not transcript:
            continue
        if looks_like_speech(transcript):
            message.body = transcript
            message.save(update_fields=['body'])
        texts.append(transcript)
    return '\n'.join(texts) or AUDIO_PLACEHOLDER


def _maybe_prompt_incomplete_intake(
    conversation: Conversation,
    channel: str = Message.Channel.WEB,
) -> str | None:
    if conversation.order_id:
        return None
    has_text, has_audio = _customer_intake_parts(conversation)
    prompt = _intake_incomplete_prompt(has_text, has_audio)
    if not prompt:
        return None
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=prompt,
        channel=channel,
    )
    return prompt


def _labeler_text_for_message(customer_message: Message, body: str) -> str:
    """Prefer typed text, then Whisper transcript, then the audio placeholder."""
    from ai.labeler import AUDIO_PLACEHOLDER
    from ai.stt import looks_like_speech, transcribe_audio

    labeler_text = body.strip()
    if labeler_text:
        return labeler_text

    if customer_message.audio:
        transcript = transcribe_audio(customer_message.audio)
        if transcript:
            if looks_like_speech(transcript):
                customer_message.body = transcript
                customer_message.save(update_fields=['body'])
            return transcript

    return AUDIO_PLACEHOLDER


def process_chat_message(
    customer: Customer,
    body: str,
    audio=None,
    conversation: Conversation | None = None,
    channel: str = Message.Channel.WEB,
    wa_message_id: str | None = None,
) -> ProcessChatResult:
    """
    Save on the current conversation, then Labeler binds, stays, or forks.
    Dumb fallback binds in place (or appends if already bound). Never copies.
    """
    from ai.labeler import classify_message
    from ai.llm import is_llm_configured

    if conversation is None:
        conversation = get_or_create_current_conversation(customer)

    assert_order_chat_open(conversation.order)

    customer_message = Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.CUSTOMER,
        body=body.strip(),
        audio=audio,
        channel=channel,
        wa_message_id=wa_message_id,
    )

    if _maybe_prompt_incomplete_intake(conversation, channel=channel):
        return ProcessChatResult(route='incomplete_intake')

    if not is_llm_configured():
        if conversation.order_id:
            return ProcessChatResult(
                route='existing_order',
                order_id=conversation.order_id,
            )
        order = _bind_conversation_to_new_order(
            conversation, customer, _labeler_text_for_intake(conversation),
        )
        return ProcessChatResult(
            route='dumb_fallback',
            order_id=order.pk,
            redirect=True,
        )

    labeler_text = (
        _labeler_text_for_intake(conversation)
        if conversation.order_id is None
        else _labeler_text_for_message(customer_message, body)
    )
    open_orders = _open_orders_for_labeler(customer)

    try:
        result = classify_message(
            customer,
            labeler_text,
            open_orders,
            current_order_id=conversation.order_id,
        )
    except Exception:
        result = None

    bound = conversation.order_id is not None

    if bound:
        if result is not None and result.route == 'new_request':
            order = _fork_conversation_for_new_order(
                conversation, customer_message, customer, labeler_text,
            )
            return ProcessChatResult(
                route='new_request',
                order_id=order.pk,
                redirect=True,
            )
        return ProcessChatResult(
            route='existing_order',
            order_id=conversation.order_id,
        )

    if result is None or result.route == 'new_request':
        order = _bind_conversation_to_new_order(conversation, customer, labeler_text)
        return ProcessChatResult(
            route='new_request',
            order_id=order.pk,
            redirect=True,
        )

    if result.route == 'existing_order' and result.order_id:
        order = Order.objects.get(pk=result.order_id, customer=customer)
        dest = _ensure_conversation(order)
        if dest.pk != conversation.pk:
            customer_message.conversation = dest
            customer_message.save(update_fields=['conversation'])
        return ProcessChatResult(
            route='existing_order',
            order_id=order.pk,
            redirect=True,
        )

    reply = result.reply or 'أهلاً! احكيلنا عن مشكلة العربية لو محتاج صيانة.'
    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=reply,
        channel=Message.Channel.WEB,
    )
    return ProcessChatResult(route='irrelevant')


def customer_has_open_orders(customer: Customer) -> bool:
    return _open_orders_queryset(customer).exists()
