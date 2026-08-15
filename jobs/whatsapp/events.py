"""WhatsApp customer notifications. Paymob is imported lazily to avoid cycles."""

from jobs.models import Order
from jobs.whatsapp.copy import (
    paid_whatsapp_text,
    progress_whatsapp_text,
    quote_whatsapp_text,
    ready_whatsapp_text,
    step_done_whatsapp_text,
)
from jobs.whatsapp.outbound import customer_uses_whatsapp, notify_order_whatsapp


def _checkout_url(order: Order) -> str | None:
    # Late import: payments.services.notify_paid imports this module.
    from payments.services import ensure_checkout_url

    return ensure_checkout_url(order)


def notify_quote(order: Order) -> None:
    if not customer_uses_whatsapp(order.customer):
        return
    url = _checkout_url(order) if order.status == Order.Status.QUOTED else None
    notify_order_whatsapp(order, quote_whatsapp_text(order, checkout_url=url))


def notify_progress(order: Order) -> None:
    if not customer_uses_whatsapp(order.customer):
        return
    url = _checkout_url(order) if order.status == Order.Status.QUOTED else None
    notify_order_whatsapp(order, progress_whatsapp_text(order, checkout_url=url))


def notify_step_done(order: Order, step_title: str) -> None:
    notify_order_whatsapp(order, step_done_whatsapp_text(order, step_title))


def notify_ready(order: Order) -> None:
    notify_order_whatsapp(order, ready_whatsapp_text(order))


def notify_paid(order: Order) -> None:
    notify_order_whatsapp(order, paid_whatsapp_text(order))


def notify_mechanic_reply(order: Order, body: str) -> None:
    notify_order_whatsapp(order, body)
