"""Order lifecycle helpers — intake and quote snapshot."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Customer
from catalog.models import Diagnostic
from jobs.models import Conversation, Message, Order, OrderStep

MAX_AUDIO_BYTES = 10 * 1024 * 1024

OPEN_ORDER_STATUSES = (
    Order.Status.PENDING_REVIEW,
    Order.Status.QUOTED,
    Order.Status.IN_PROGRESS,
    Order.Status.READY_FOR_PICKUP,
)

Route = Literal['new_request', 'existing_order', 'irrelevant', 'dumb_fallback']


@dataclass
class ProcessChatResult:
    route: Route
    order_id: int | None = None
    redirect: bool = False


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
) -> Order:
    """Dumb intake: bind the current conversation to a new pending_review order."""
    if conversation is None:
        conversation = get_or_create_current_conversation(customer)
    if conversation.order_id:
        Message.objects.create(
            conversation=conversation,
            author_type=Message.AuthorType.CUSTOMER,
            body=body.strip(),
            audio=audio,
            channel=Message.Channel.WEB,
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
        channel=Message.Channel.WEB,
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
            body='__ready__\nالعربية جاهزة للاستلام — تقدر تيجي الورشة.',
            channel=Message.Channel.WEB,
        )

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
        body='__ready__\nالعربية جاهزة للاستلام — تقدر تيجي الورشة.',
        channel=Message.Channel.WEB,
    )

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
        body='تم استلام العربية — شكراً لثقتك في ورشة كريم.',
        channel=Message.Channel.WEB,
    )

    return order


def piasters_from_egp(amount: Decimal) -> int:
    return int(amount * 100)


def egp_from_piasters(piasters: int) -> Decimal:
    return Decimal(piasters) / 100


def get_or_create_current_conversation(customer: Customer) -> Conversation:
    """Open order chat if any; else unbound intake; never mint a ghost inbox while a job is open."""
    open_conversation = (
        Conversation.objects.filter(
            customer=customer,
            order__status__in=OPEN_ORDER_STATUSES,
        )
        .order_by('-created_at')
        .first()
    )
    if open_conversation:
        return open_conversation

    unbound = Conversation.objects.filter(
        customer=customer,
        order__isnull=True,
    ).order_by('-created_at').first()
    if unbound:
        return unbound
    return Conversation.objects.create(customer=customer, order=None)


def get_or_create_intake_conversation(customer: Customer) -> Conversation:
    return get_or_create_current_conversation(customer)


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


def _bind_conversation_to_new_order(
    conversation: Conversation,
    customer: Customer,
    labeler_text: str,
) -> Order:
    from ai.tagger import suggest_labels_from_db

    order = Order.objects.create(
        customer=customer,
        status=Order.Status.PENDING_REVIEW,
    )
    conversation.order = order
    conversation.save(update_fields=['order'])
    label_ids = suggest_labels_from_db(labeler_text)
    if label_ids:
        order.labels.set(label_ids)
    return order


def _fork_conversation_for_new_order(
    parent: Conversation,
    triggering_message: Message,
    customer: Customer,
    labeler_text: str,
) -> Order:
    from ai.tagger import suggest_labels_from_db

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
    label_ids = suggest_labels_from_db(labeler_text)
    if label_ids:
        order.labels.set(label_ids)
    return order


def post_mechanic_message(order: Order, body: str, audio=None) -> Message:
    conversation = _ensure_conversation(order)
    return Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.MECHANIC,
        body=body.strip(),
        audio=audio,
        channel=Message.Channel.WEB,
    )


def process_chat_message(
    customer: Customer,
    body: str,
    audio=None,
    conversation: Conversation | None = None,
) -> ProcessChatResult:
    """
    Save on the current conversation, then Labeler binds, stays, or forks.
    Dumb fallback binds in place (or appends if already bound). Never copies.
    """
    from ai.labeler import AUDIO_PLACEHOLDER, classify_message
    from ai.llm import is_llm_configured

    if conversation is None:
        conversation = get_or_create_current_conversation(customer)

    if not is_llm_configured():
        order = create_order_from_intake(
            customer, body, audio=audio, conversation=conversation,
        )
        return ProcessChatResult(
            route='dumb_fallback',
            order_id=order.pk,
            redirect=True,
        )

    customer_message = Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.CUSTOMER,
        body=body.strip(),
        audio=audio,
        channel=Message.Channel.WEB,
    )

    labeler_text = body.strip() or AUDIO_PLACEHOLDER
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
