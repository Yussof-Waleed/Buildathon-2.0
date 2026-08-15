"""Route customer chat messages: new_request, existing_order, or irrelevant."""

from dataclasses import dataclass
from typing import Literal

from accounts.models import Customer
from ai.llm import LLMError, LLMNotConfiguredError, complete_json

Route = Literal['new_request', 'existing_order', 'irrelevant']

AUDIO_PLACEHOLDER = '(رسالة صوتية من العميل)'


@dataclass
class LabelerResult:
    route: Route
    order_id: int | None = None
    reply: str = ''


def classify_message(
    customer: Customer,
    text: str,
    open_orders: list[dict],
    current_order_id: int | None = None,
) -> LabelerResult:
    """
    open_orders: list of {id, status, summary} for this customer's open orders.
    current_order_id: this conversation's bound order, or None if intake.
    """
    orders_block = '\n'.join(
        f'- id={o["id"]}, status={o["status"]}, summary={o["summary"]}'
        for o in open_orders
    ) or '(none)'

    current_block = (
        f'This message was sent on the dedicated chat for order id={current_order_id}. '
        'Use new_request ONLY if the customer is starting a different repair '
        '(another car or an unrelated job), not a follow-up, status question, '
        'photo, haggle, or greeting about the current job.'
        if current_order_id
        else 'This message was sent on an unbound intake chat (no order yet).'
    )

    prompt = f"""You route messages for Warsha, a neighbourhood car repair garage in Cairo (Arabic customers).

Customer phone: {customer.phone}

{current_block}

Open orders for this customer (only these ids are valid for existing_order):
{orders_block}

Customer message:
{text}

Classify the message. Return ONLY valid JSON with this shape:
{{
  "route": "new_request" | "existing_order" | "irrelevant",
  "order_id": null or integer (required when route is existing_order, must match an open order id),
  "reply": "" or short Arabic reply (required when route is irrelevant — friendly garage tone, 1-2 sentences)
}}

Rules:
- new_request: customer describes a car problem, wants repair, booking, quote, or sends engine/audio issue
- On a bound order chat, new_request means a DIFFERENT repair — not "is it ready?", extra details, or chat about the current job
- existing_order: follow-up about an open order already listed above (on a bound chat, use this for the current job)
- irrelevant: greetings, thanks, off-topic — reply in Arabic as reply field (intake only; on a bound chat prefer existing_order)
- reply must be Arabic when irrelevant
- order_id must be null unless route is existing_order
"""

    try:
        data = complete_json(prompt)
    except (LLMNotConfiguredError, LLMError, ValueError, TypeError):
        raise

    if not isinstance(data, dict):
        raise ValueError('Labeler returned non-object JSON')

    route = data.get('route', '')
    if route not in ('new_request', 'existing_order', 'irrelevant'):
        raise ValueError(f'Invalid route: {route}')

    order_id = data.get('order_id')
    if order_id is not None:
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            order_id = None

    reply = (data.get('reply') or '').strip()

    if current_order_id and route == 'irrelevant':
        route = 'existing_order'
        order_id = current_order_id

    if route == 'existing_order':
        valid_ids = {o['id'] for o in open_orders}
        if order_id not in valid_ids:
            if current_order_id in valid_ids:
                order_id = current_order_id
            elif open_orders:
                order_id = open_orders[0]['id']
            else:
                route = 'new_request'
                order_id = None

    return LabelerResult(route=route, order_id=order_id, reply=reply)
