from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.shortcuts import get_object_or_404, redirect, render

from accounts.customer_session import get_customer, login_customer, require_customer
from jobs.models import Order
from jobs.services import (
    _ensure_conversation,
    _get_conversation,
    customer_has_open_orders,
    get_or_create_intake_conversation,
    process_chat_message,
    validate_audio_upload,
)
from payments.paymob_config import get_paymob_readiness

ACTIVE_POLL_STATUSES = frozenset({
    Order.Status.PENDING_REVIEW,
    Order.Status.QUOTED,
    Order.Status.PAID,
    Order.Status.IN_PROGRESS,
    Order.Status.READY_FOR_PICKUP,
})


def home(request):
    paymob = get_paymob_readiness()
    return render(request, 'shared/home.html', {'paymob': paymob})


def _chat_context(customer, error=None):
    conversation = get_or_create_intake_conversation(customer)
    thread_messages = conversation.messages.all()
    poll_thread = customer_has_open_orders(customer)
    return {
        'customer': customer,
        'nav_active': 'chat',
        'thread_messages': thread_messages,
        'poll_thread': poll_thread,
        'error': error,
        'order': conversation.order,
    }


def customer_home(request):
    customer = get_customer(request)

    if request.method == 'POST':
        if customer is None:
            raw_phone = request.POST.get('phone', '').strip()
            if not raw_phone:
                return render(
                    request,
                    'customer/phone_gate.html',
                    {'error': _('Enter your mobile number.')},
                )
            try:
                login_customer(request, raw_phone)
            except ValidationError:
                return render(
                    request,
                    'customer/phone_gate.html',
                    {
                        'error': _(
                            'Invalid number. Example: \u206601012345678\u2069 or '
                            '\u2066+201012345678\u2069'
                        ),
                    },
                )
            return redirect('customer-chat')

        body = request.POST.get('body', '').strip()
        audio = request.FILES.get('audio')

        if not body or not audio:
            return render(
                request,
                'customer/chat.html',
                _chat_context(
                    get_customer(request),
                    error=_('Send a written description and a voice note of the problem.'),
                ),
            )

        try:
            validate_audio_upload(audio)
        except ValidationError as exc:
            return render(
                request,
                'customer/chat.html',
                _chat_context(get_customer(request), error=exc.messages[0]),
            )

        result = process_chat_message(get_customer(request), body, audio=audio)
        if result.redirect and result.order_id:
            return redirect('customer-order-detail', order_id=result.order_id)

        return render(request, 'customer/chat.html', _chat_context(get_customer(request)))

    if customer is None:
        return render(request, 'customer/phone_gate.html')

    return render(request, 'customer/chat.html', _chat_context(customer))


@require_customer
def customer_chat_thread(request):
    customer = get_customer(request)
    conversation = get_or_create_intake_conversation(customer)
    return render(
        request,
        'shared/partials/message_thread.html',
        {
            'thread_messages': conversation.messages.all(),
            'order': conversation.order,
            'viewer': 'customer',
        },
    )


@require_customer
def customer_orders_list(request):
    customer = get_customer(request)
    orders = (
        Order.objects.filter(customer=customer)
        .select_related('diagnostic')
        .prefetch_related('steps')
        .order_by('-created_at')
    )
    return render(
        request,
        'customer/orders_list.html',
        {
            'orders': orders,
            'customer': customer,
            'nav_active': 'orders',
        },
    )


@require_customer
def customer_order_detail(request, order_id):
    customer = get_customer(request)
    order = get_object_or_404(
        Order.objects.select_related('customer', 'diagnostic').prefetch_related(
            'steps',
            'conversation__messages',
        ),
        pk=order_id,
        customer=customer,
    )
    conversation = _get_conversation(order)
    messages_list = conversation.messages.all() if conversation else []
    can_cancel = order.status in (
        Order.Status.PENDING_REVIEW,
        Order.Status.QUOTED,
    )
    show_agreement = order.quoted_price is not None
    payment_return = request.GET.get('paid') == 'return'
    paymob = get_paymob_readiness()
    poll_thread = order.status in ACTIVE_POLL_STATUSES

    return render(
        request,
        'customer/order_detail.html',
        {
            'order': order,
            'customer': customer,
            'nav_active': 'orders',
            'thread_messages': messages_list,
            'can_cancel': can_cancel,
            'show_agreement': show_agreement,
            'payment_return': payment_return,
            'paymob_ready': paymob['ready'],
            'poll_thread': poll_thread,
        },
    )


@require_customer
def customer_order_thread(request, order_id):
    customer = get_customer(request)
    order = get_object_or_404(
        Order.objects.prefetch_related('conversation__messages'),
        pk=order_id,
        customer=customer,
    )
    conversation = _get_conversation(order)
    messages_list = conversation.messages.all() if conversation else []
    return render(
        request,
        'shared/partials/message_thread.html',
        {
            'thread_messages': messages_list,
            'order': order,
            'paymob_ready': get_paymob_readiness()['ready'],
            'viewer': 'customer',
        },
    )


@require_customer
def customer_order_cancel(request, order_id):
    if request.method != 'POST':
        return redirect('customer-order-detail', order_id=order_id)

    customer = get_customer(request)
    order = get_object_or_404(Order, pk=order_id, customer=customer)

    if order.status in (Order.Status.PENDING_REVIEW, Order.Status.QUOTED):
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status', 'updated_at'])

    return redirect('customer-order-detail', order_id=order_id)


@require_customer
def customer_order_message(request, order_id):
    if request.method != 'POST':
        return redirect('customer-order-detail', order_id=order_id)

    customer = get_customer(request)
    order = get_object_or_404(Order, pk=order_id, customer=customer)
    conversation = _ensure_conversation(order)

    if not order.chat_open:
        messages.error(request, _('This chat is closed — the order was cancelled.'))
        return redirect('customer-order-detail', order_id=order_id)

    body = request.POST.get('body', '').strip()
    audio = request.FILES.get('audio')

    if not body and not audio:
        return redirect('customer-order-detail', order_id=order_id)

    try:
        validate_audio_upload(audio)
        result = process_chat_message(
            customer, body, audio=audio, conversation=conversation,
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect('customer-order-detail', order_id=order_id)

    if result.redirect and result.order_id and result.order_id != order.pk:
        return redirect('customer-order-detail', order_id=result.order_id)

    return redirect('customer-order-detail', order_id=order_id)