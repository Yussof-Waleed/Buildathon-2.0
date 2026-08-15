from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from catalog.i18n import localized_field

register = template.Library()


def _message_kind(body: str) -> str:
    if not body:
        return 'empty'
    text = body.strip()
    if text.startswith('__quote__'):
        return 'quote'
    if text.startswith('__step__'):
        return 'step'
    if text.startswith('__ready__'):
        return 'ready'
    if text.startswith('__payment_failed__'):
        return 'payment_failed'
    if text.startswith('__payment__'):
        return 'payment'
    if text.startswith('__started__'):
        return 'started'
    if text.startswith('__completed__'):
        return 'completed'
    if text.startswith('[order:'):
        return 'order_link'
    return 'text'


def _parse_quote(body: str) -> dict:
    lines = body.strip().split('\n')
    title = lines[1].strip() if len(lines) > 1 else ''
    price = lines[2].strip() if len(lines) > 2 else ''
    steps = []
    note_lines = []
    for line in lines[3:]:
        if '|' in line:
            step_title, minutes = line.rsplit('|', 1)
            if minutes.strip().isdigit():
                steps.append({
                    'title': step_title.strip(),
                    'minutes': minutes.strip(),
                })
                continue
        note_lines.append(line)
    return {
        'title': title,
        'price': price,
        'steps': steps,
        'note': '\n'.join(note_lines).strip(),
    }


def _quote_from_order(order) -> dict:
    steps = [
        {
            'title': step.localized_title,
            'minutes': str(step.expected_minutes),
            'description': step.localized_description,
        }
        for step in order.steps.all()
    ]
    return {
        'title': order.localized_quoted_title,
        'price': str(order.quoted_price),
        'steps': steps,
        'note': order.kareem_note or '',
    }


def _step_title_from_order(order, body: str) -> str:
    parsed_title = _body_after_prefix(body)
    if not order:
        return parsed_title
    for step in order.steps.all():
        if step.title_en == parsed_title or step.title_ar == parsed_title:
            return step.localized_title
    return parsed_title


def _parse_order_link(body: str) -> dict:
    text = body.strip()
    bracket = text.index(']')
    order_id = int(text[7:bracket])
    rest = text[bracket + 1:].strip()
    return {'order_id': order_id, 'text': rest}


def _body_after_prefix(body: str) -> str:
    text = body.strip()
    if '\n' in text:
        return text.split('\n', 1)[1].strip()
    return (
        text.replace('__step__', '')
        .replace('__ready__', '')
        .replace('__payment_failed__', '')
        .replace('__payment__', '')
        .replace('__started__', '')
        .replace('__completed__', '')
        .strip()
    )


@register.filter
def localized(obj, field: str) -> str:
    return localized_field(obj, field)


@register.filter
def piasters_egp(piasters) -> str:
    if piasters is None:
        return '0.00'
    return f'{int(piasters) / 100:.2f}'


def _message_bubble_context(message, order=None, paymob_ready=False, viewer='customer'):
    body = message.body or ''
    kind = _message_kind(body)
    ctx = {
        'message': message,
        'kind': kind,
        'viewer': viewer,
        'order': order,
        'paymob_ready': paymob_ready,
        'show_pay': (
            kind == 'quote'
            and order is not None
            and order.status == 'quoted'
            and paymob_ready
        ),
        'show_pay_waiting': (
            kind == 'quote'
            and order is not None
            and order.status == 'quoted'
            and not paymob_ready
        ),
    }
    if kind == 'quote':
        if order and order.quoted_price is not None:
            ctx['quote'] = _quote_from_order(order)
        else:
            ctx['quote'] = _parse_quote(body)
    elif kind == 'step':
        ctx['step_title'] = _step_title_from_order(order, body)
    elif kind == 'order_link':
        ctx['order_link'] = _parse_order_link(body)
    elif kind == 'ready':
        ctx['text'] = _('Your car is ready for pickup — come to the workshop.')
    elif kind == 'payment':
        ctx['text'] = _('Payment confirmed — Kareem will start when he is ready.')
    elif kind == 'payment_failed':
        ctx['text'] = _('Payment failed — try again or message Kareem.')
    elif kind == 'started':
        ctx['text'] = _('Kareem started work on your order.')
    elif kind == 'completed':
        ctx['text'] = _('Car collected — thank you for trusting Warsha.')
    elif kind == 'text':
        ctx['text'] = body
    return ctx


@register.simple_tag(takes_context=True)
def message_bubble(context, message, order=None, paymob_ready=False, viewer='customer'):
    # Inclusion tags copy RequestContext and crash on Python 3.14 + Django 5.1.
    ctx = _message_bubble_context(message, order, paymob_ready, viewer)
    ctx['csrf_token'] = context.get('csrf_token')
    return mark_safe(
        render_to_string(
            'shared/partials/message_bubble.html',
            ctx,
            request=context.get('request'),
        )
    )


@register.filter
def author_label(author_type: str, viewer: str = 'customer') -> str:
    if author_type == 'customer':
        return _('You') if viewer == 'customer' else _('Customer')
    if author_type in ('mechanic', 'system'):
        return _('Kareem')
    return ''
