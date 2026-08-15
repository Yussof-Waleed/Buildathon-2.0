"""Payment state transitions — webhook is source of truth."""

from django.db import IntegrityError, transaction

from jobs.models import Conversation, Message, Order
from payments.models import Payment


def _ensure_conversation(order: Order) -> Conversation:
    conversation = order.conversations.first()
    if conversation:
        return conversation
    return Conversation.objects.create(
        customer=order.customer,
        order=order,
    )


def apply_successful_payment(
    order_id: int,
    paymob_transaction_id: str,
    amount_piasters: int,
    intention_id: str = '',
) -> bool:
    """
    Mark order paid and in_progress. Idempotent on paymob_transaction_id.
    Returns True if payment was applied (or already applied).
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        if Payment.objects.filter(paymob_transaction_id=paymob_transaction_id).exists():
            return True

        if order.status == Order.Status.IN_PROGRESS:
            return True

        if order.status != Order.Status.QUOTED:
            return False

        try:
            Payment.objects.create(
                order=order,
                amount_piasters=amount_piasters,
                status=Payment.Status.PAID,
                paymob_intention_id=intention_id,
                paymob_transaction_id=paymob_transaction_id,
            )
        except IntegrityError:
            return True

        order.status = Order.Status.IN_PROGRESS
        order.save(update_fields=['status', 'updated_at'])

        conversation = _ensure_conversation(order)
        Message.objects.create(
            conversation=conversation,
            author_type=Message.AuthorType.SYSTEM,
            body='تم تأكيد الدفع. كريم بدأ العمل على طلبك.',
            channel=Message.Channel.WEB,
        )

    return True


def apply_failed_payment(
    order_id: int,
    paymob_transaction_id: str,
    amount_piasters: int,
    intention_id: str = '',
) -> None:
    """Record failed payment without changing order status from quoted."""
    with transaction.atomic():
        if Payment.objects.filter(paymob_transaction_id=paymob_transaction_id).exists():
            return

        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return

        pending = Payment.objects.filter(
            order=order,
            status=Payment.Status.PENDING,
        ).order_by('-created_at').first()

        if pending:
            pending.status = Payment.Status.FAILED
            pending.paymob_transaction_id = paymob_transaction_id
            if intention_id:
                pending.paymob_intention_id = intention_id
            pending.save()
        else:
            try:
                Payment.objects.create(
                    order=order,
                    amount_piasters=amount_piasters,
                    status=Payment.Status.FAILED,
                    paymob_intention_id=intention_id,
                    paymob_transaction_id=paymob_transaction_id,
                )
            except IntegrityError:
                pass


def extract_order_id_from_callback(obj: dict) -> int | None:
    """Resolve Warsha order id from Paymob callback obj."""
    order_data = obj.get('order') or {}
    candidates = [
        order_data.get('merchant_order_id'),
        obj.get('merchant_order_id'),
        obj.get('special_reference'),
    ]
    extras = obj.get('extras') or {}
    if isinstance(extras, dict):
        candidates.append(extras.get('merchant_order_id'))

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return int(str(candidate).strip())
        except (TypeError, ValueError):
            continue
    return None
