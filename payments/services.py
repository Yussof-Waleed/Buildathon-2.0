"""Payment state transitions — webhook is source of truth."""

import logging

from django.db import IntegrityError, transaction

from jobs.models import Conversation, Message, Order
from payments.models import Payment

logger = logging.getLogger(__name__)


def _ensure_conversation(order: Order) -> Conversation:
    try:
        return order.conversation
    except Conversation.DoesNotExist:
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
    Record a paid Payment and move quoted → paid.
    Does not start work — Kareem clicks Start work for that.
    Idempotent on paymob_transaction_id.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        if Payment.objects.filter(paymob_transaction_id=paymob_transaction_id).exists():
            return True

        if order.status == Order.Status.PAID:
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

        order.status = Order.Status.PAID
        order.save(update_fields=['status', 'updated_at'])

        conversation = _ensure_conversation(order)
        Message.objects.create(
            conversation=conversation,
            author_type=Message.AuthorType.MECHANIC,
            body='__payment__',
            channel=Message.Channel.WEB,
        )

    # Late import: jobs.whatsapp.events pulls checkout helpers from this module.
    from jobs.whatsapp.events import notify_paid

    notify_paid(order)
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

        recorded = False
        if pending:
            pending.status = Payment.Status.FAILED
            pending.paymob_transaction_id = paymob_transaction_id
            if intention_id:
                pending.paymob_intention_id = intention_id
            pending.save()
            recorded = True
        else:
            try:
                Payment.objects.create(
                    order=order,
                    amount_piasters=amount_piasters,
                    status=Payment.Status.FAILED,
                    paymob_intention_id=intention_id,
                    paymob_transaction_id=paymob_transaction_id,
                )
                recorded = True
            except IntegrityError:
                pass

        if recorded:
            conversation = _ensure_conversation(order)
            Message.objects.create(
                conversation=conversation,
                author_type=Message.AuthorType.MECHANIC,
                body='فشل الدفع — جرّب مرة أخرى أو تواصل مع كريم.',
                channel=Message.Channel.WEB,
            )


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


def ensure_checkout_url(order: Order) -> str | None:
    """Create a Paymob Unified Checkout URL and keep a pending Payment row."""
    if order.status != Order.Status.QUOTED or order.quoted_price is None:
        return None

    from payments.paymob import (
        PaymobAPIError,
        PaymobNotConfiguredError,
        create_payment_intention,
    )

    try:
        checkout_url, intention_id = create_payment_intention(order)
    except PaymobNotConfiguredError:
        logger.info('Paymob is not configured — skipping checkout URL for order %s', order.pk)
        return None
    except PaymobAPIError:
        logger.exception('Paymob intention failed for order %s', order.pk)
        return None

    amount_piasters = int(order.quoted_price * 100)
    pending = Payment.objects.filter(
        order=order,
        status=Payment.Status.PENDING,
    ).order_by('-created_at').first()

    if pending:
        pending.amount_piasters = amount_piasters
        pending.paymob_intention_id = intention_id
        pending.save(update_fields=['amount_piasters', 'paymob_intention_id'])
    else:
        Payment.objects.create(
            order=order,
            amount_piasters=amount_piasters,
            status=Payment.Status.PENDING,
            paymob_intention_id=intention_id,
        )
    return checkout_url
