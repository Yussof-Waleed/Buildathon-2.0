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


def _ensure_conversation(order: Order) -> Conversation:
    conversation = order.conversations.first()
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
) -> Order:
    """Dumb intake: every message creates a new pending_review order."""
    order = Order.objects.create(
        customer=customer,
        status=Order.Status.PENDING_REVIEW,
    )
    conversation = Conversation.objects.create(
        customer=customer,
        order=order,
    )
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
    order.quoted_price = diagnostic.price
    order.kareem_note = kareem_note
    order.status = Order.Status.QUOTED
    order.save()

    order.steps.all().delete()
    OrderStep.objects.bulk_create([
        OrderStep(
            order=order,
            title=step.title,
            description=step.description,
            expected_minutes=step.expected_minutes,
            sort_order=step.sort_order,
        )
        for step in diagnostic.steps.all()
    ])

    conversation = order.conversations.first()
    if not conversation:
        conversation = Conversation.objects.create(
            customer=order.customer,
            order=order,
        )

    steps_text = '\n'.join(
        f'- {s.title} (~{s.expected_minutes} min)'
        for s in order.steps.all()
    )
    body = (
        f'Diagnostic: {diagnostic.name}\n'
        f'Price: {order.quoted_price} EGP\n'
        f'Steps:\n{steps_text}'
    )
    if kareem_note:
        body += f'\n\nNote from Kareem: {kareem_note}'

    Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.SYSTEM,
        body=body,
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
        author_type=Message.AuthorType.SYSTEM,
        body=f'تم إنجاز: {step.title}',
        channel=Message.Channel.WEB,
    )

    if not order.steps.filter(completed_at__isnull=True).exists():
        order.status = Order.Status.READY_FOR_PICKUP
        order.save(update_fields=['status', 'updated_at'])
        Message.objects.create(
            conversation=conversation,
            author_type=Message.AuthorType.SYSTEM,
            body='العربية جاهزة للاستلام — تقدر تيجي الورشة.',
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
        author_type=Message.AuthorType.SYSTEM,
        body='العربية جاهزة للاستلام — تقدر تيجي الورشة.',
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
        author_type=Message.AuthorType.SYSTEM,
        body='تم استلام العربية — شكراً لثقتك في ورشة كريم.',
        channel=Message.Channel.WEB,
    )

    return order


def piasters_from_egp(amount: Decimal) -> int:
    return int(amount * 100)


def egp_from_piasters(piasters: int) -> Decimal:
    return Decimal(piasters) / 100


def get_or_create_intake_conversation(customer: Customer) -> Conversation:
    conversation = Conversation.objects.filter(
        customer=customer,
        order__isnull=True,
    ).first()
    if conversation:
        return conversation
    return Conversation.objects.create(customer=customer, order=None)


def _open_orders_queryset(customer: Customer):
    return Order.objects.filter(
        customer=customer,
        status__in=OPEN_ORDER_STATUSES,
    ).order_by('-created_at')


def _order_summary(order: Order) -> str:
    conversation = order.conversations.first()
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


def _copy_customer_message_to_order(
    order: Order,
    body: str,
    audio=None,
) -> Message:
    conversation = _ensure_conversation(order)
    return Message.objects.create(
        conversation=conversation,
        author_type=Message.AuthorType.CUSTOMER,
        body=body.strip(),
        audio=audio,
        channel=Message.Channel.WEB,
    )


def process_chat_message(
    customer: Customer,
    body: str,
    audio=None,
) -> ProcessChatResult:
    """
    Route intake via Labeler when LLM configured; else dumb new order + redirect.
    Always records customer message on intake conversation when using AI path.
    """
    from ai.labeler import AUDIO_PLACEHOLDER, classify_message
    from ai.llm import is_llm_configured
    from ai.tagger import suggest_labels_from_db

    if not is_llm_configured():
        order = create_order_from_intake(customer, body, audio=audio)
        return ProcessChatResult(
            route='dumb_fallback',
            order_id=order.pk,
            redirect=True,
        )

    intake = get_or_create_intake_conversation(customer)
    Message.objects.create(
        conversation=intake,
        author_type=Message.AuthorType.CUSTOMER,
        body=body.strip(),
        audio=audio,
        channel=Message.Channel.WEB,
    )

    labeler_text = body.strip() or AUDIO_PLACEHOLDER
    open_orders = _open_orders_for_labeler(customer)

    try:
        result = classify_message(customer, labeler_text, open_orders)
    except Exception:
        result = None

    if result is None or result.route == 'new_request':
        order = Order.objects.create(
            customer=customer,
            status=Order.Status.PENDING_REVIEW,
        )
        _copy_customer_message_to_order(order, body, audio=audio)
        label_ids = suggest_labels_from_db(labeler_text)
        if label_ids:
            order.labels.set(label_ids)
        Message.objects.create(
            conversation=intake,
            author_type=Message.AuthorType.SYSTEM,
            body=_intake_order_link_body(
                order.pk,
                'تم إنشاء طلبك — تابع من هنا',
            ),
            channel=Message.Channel.WEB,
        )
        return ProcessChatResult(route='new_request', order_id=order.pk)

    if result.route == 'existing_order' and result.order_id:
        order = Order.objects.get(pk=result.order_id, customer=customer)
        _copy_customer_message_to_order(order, body, audio=audio)
        Message.objects.create(
            conversation=intake,
            author_type=Message.AuthorType.SYSTEM,
            body=_intake_order_link_body(
                order.pk,
                'تم إضافة رسالتك على الطلب',
            ),
            channel=Message.Channel.WEB,
        )
        return ProcessChatResult(route='existing_order', order_id=order.pk)

    reply = result.reply or 'أهلاً! احكيلنا عن مشكلة العربية لو محتاج صيانة.'
    Message.objects.create(
        conversation=intake,
        author_type=Message.AuthorType.MECHANIC,
        body=reply,
        channel=Message.Channel.WEB,
    )
    return ProcessChatResult(route='irrelevant')


def customer_has_open_orders(customer: Customer) -> bool:
    return _open_orders_queryset(customer).exists()
