from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from catalog.models import Diagnostic
from jobs.kareem_analytics import order_status_counts, payment_summary
from jobs.models import Message, Order
from jobs.services import (
    _get_conversation,
    complete_order_step,
    mark_order_completed,
    mark_ready_for_pickup,
    piasters_from_egp,
    post_mechanic_message,
    snapshot_diagnostic_on_order,
    start_order_work,
    validate_audio_upload,
)
from jobs.views import ACTIVE_POLL_STATUSES
from payments.models import Payment
from payments.services import apply_successful_payment


def staff_required(view_func):
    @wraps(view_func)
    @login_required(login_url='/k/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect('kareem-login')
        return view_func(request, *args, **kwargs)

    return wrapper


class KareemLoginView(LoginView):
    template_name = 'mechanic/login.html'
    redirect_authenticated_user = True


class KareemLogoutView(LogoutView):
    next_page = '/k/login/'


@staff_required
def kareem_overview(request):
    status_counts = order_status_counts()
    pay_summary = payment_summary()
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:5]
    recent_payments = Payment.objects.select_related(
        'order', 'order__customer',
    ).order_by('-created_at')[:5]

    return render(
        request,
        'mechanic/overview.html',
        {
            'nav_active': 'overview',
            'status_counts': status_counts,
            'pay_summary': pay_summary,
            'recent_orders': recent_orders,
            'recent_payments': recent_payments,
        },
    )


@staff_required
def kareem_money(request):
    status_filter = request.GET.get('status', '').strip()
    date_filter = request.GET.get('date', 'all').strip()

    payments = Payment.objects.select_related(
        'order', 'order__customer',
    ).order_by('-created_at')

    if status_filter in dict(Payment.Status.choices):
        payments = payments.filter(status=status_filter)

    today = timezone.localdate()
    if date_filter == 'today':
        payments = payments.filter(created_at__date=today)
    elif date_filter == 'week':
        week_start = today - timezone.timedelta(days=7)
        payments = payments.filter(created_at__date__gte=week_start)

    return render(
        request,
        'mechanic/money.html',
        {
            'nav_active': 'money',
            'payments': payments,
            'status_filter': status_filter,
            'date_filter': date_filter,
            'status_choices': Payment.Status.choices,
            'pay_summary': payment_summary(),
        },
    )


@staff_required
def kareem_requests_list(request):
    status_filter = request.GET.get('status', '').strip()
    from_whatsapp = Exists(
        Message.objects.filter(
            conversation__order_id=OuterRef('pk'),
            channel=Message.Channel.WHATSAPP,
        )
    )
    orders = (
        Order.objects.select_related('customer')
        .prefetch_related('labels')
        .annotate(from_whatsapp=from_whatsapp)
        .order_by('-created_at')
    )
    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(
        request,
        'mechanic/requests_list.html',
        {
            'nav_active': 'requests',
            'orders': orders,
            'status_filter': status_filter,
            'status_choices': Order.Status.choices,
            'pending_count': Order.objects.filter(
                status=Order.Status.PENDING_REVIEW,
            ).count(),
            'quoted_count': Order.objects.filter(status=Order.Status.QUOTED).count(),
            'paid_count': Order.objects.filter(status=Order.Status.PAID).count(),
            'in_progress_count': Order.objects.filter(
                status=Order.Status.IN_PROGRESS,
            ).count(),
        },
    )


@staff_required
def kareem_request_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('customer', 'diagnostic').prefetch_related(
            'steps',
            'labels',
            'conversation__messages',
        ),
        pk=order_id,
    )
    conversation = _get_conversation(order)
    message_list = conversation.messages.all() if conversation else []
    from_whatsapp = any(
        message.channel == Message.Channel.WHATSAPP for message in message_list
    )
    diagnostics = Diagnostic.objects.prefetch_related('steps').order_by('title_ar')
    can_quote = order.status == Order.Status.PENDING_REVIEW
    can_confirm_paid = order.status == Order.Status.QUOTED
    can_start_work = order.status == Order.Status.PAID
    can_mark_ready = order.status == Order.Status.IN_PROGRESS
    can_mark_completed = order.status == Order.Status.READY_FOR_PICKUP
    can_complete_steps = order.status == Order.Status.IN_PROGRESS
    poll_thread = order.status in ACTIVE_POLL_STATUSES

    return render(
        request,
        'mechanic/request_detail.html',
        {
            'nav_active': 'requests',
            'order': order,
            'from_whatsapp': from_whatsapp,
            'thread_messages': message_list,
            'diagnostics': diagnostics,
            'can_quote': can_quote,
            'can_confirm_paid': can_confirm_paid,
            'can_start_work': can_start_work,
            'can_mark_ready': can_mark_ready,
            'can_mark_completed': can_mark_completed,
            'can_complete_steps': can_complete_steps,
            'poll_thread': poll_thread,
        },
    )


@staff_required
def kareem_request_thread(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('conversation__messages'),
        pk=order_id,
    )
    conversation = _get_conversation(order)
    message_list = conversation.messages.all() if conversation else []
    return render(
        request,
        'shared/partials/message_thread.html',
        {
            'thread_messages': message_list,
            'order': order,
            'viewer': 'kareem',
        },
    )


@staff_required
def kareem_request_quote(request, order_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)

    if order.status != Order.Status.PENDING_REVIEW:
        messages.error(request, _('This order cannot be quoted — status is not pending review.'))
        return redirect('kareem-request-detail', order_id=order_id)

    diagnostic_id = request.POST.get('diagnostic_id')
    if not diagnostic_id:
        messages.error(request, _('Choose a diagnostic.'))
        return redirect('kareem-request-detail', order_id=order_id)

    diagnostic = get_object_or_404(Diagnostic, pk=diagnostic_id)
    kareem_note = request.POST.get('kareem_note', '').strip()

    snapshot_diagnostic_on_order(order, diagnostic, kareem_note)
    messages.success(
        request,
        _('Quote sent — %(price)s EGP') % {'price': diagnostic.price},
    )

    return redirect('kareem-request-detail', order_id=order_id)


@staff_required
def kareem_confirm_paid(request, order_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)

    if order.status != Order.Status.QUOTED:
        messages.error(request, _('Payment cannot be confirmed for this order.'))
        return redirect('kareem-request-detail', order_id=order_id)

    transaction_id = f'dev-{order_id}-{int(timezone.now().timestamp())}'
    amount_piasters = piasters_from_egp(order.quoted_price)
    apply_successful_payment(
        order.pk,
        transaction_id,
        amount_piasters,
    )
    messages.success(request, _('Payment confirmed — start work when you are ready.'))
    return redirect('kareem-request-detail', order_id=order_id)


@staff_required
def kareem_start_work(request, order_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)

    if order.status != Order.Status.PAID:
        messages.error(request, _('Work can start only after payment is confirmed.'))
        return redirect('kareem-request-detail', order_id=order_id)

    start_order_work(order)
    messages.success(request, _('Work started.'))
    return redirect('kareem-request-detail', order_id=order_id)


@staff_required
def kareem_mark_ready(request, order_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)

    if order.status != Order.Status.IN_PROGRESS:
        messages.error(request, _('Order cannot be marked ready for pickup.'))
        return redirect('kareem-request-detail', order_id=order_id)

    mark_ready_for_pickup(order)
    messages.success(request, _('Order marked ready for pickup — customer notified.'))
    return redirect('kareem-request-detail', order_id=order_id)


@staff_required
def kareem_complete_step(request, order_id, step_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)

    if order.status != Order.Status.IN_PROGRESS:
        messages.error(request, _('Steps cannot be completed before work starts.'))
        return redirect('kareem-request-detail', order_id=order_id)

    if not order.steps.filter(pk=step_id).exists():
        messages.error(request, _('Step not found.'))
        return redirect('kareem-request-detail', order_id=order_id)

    complete_order_step(order, step_id)
    order.refresh_from_db()
    if order.status == Order.Status.READY_FOR_PICKUP:
        messages.success(request, _('All steps done — order ready for pickup.'))
    else:
        messages.success(request, _('Step completed.'))
    return redirect('kareem-request-detail', order_id=order_id)


@staff_required
def kareem_mark_completed(request, order_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)

    if order.status != Order.Status.READY_FOR_PICKUP:
        messages.error(request, _('Order cannot be marked completed.'))
        return redirect('kareem-request-detail', order_id=order_id)

    mark_order_completed(order)
    messages.success(request, _('Order completed — car collected.'))
    return redirect('kareem-request-detail', order_id=order_id)


@staff_required
def kareem_request_message(request, order_id):
    if request.method != 'POST':
        return redirect('kareem-request-detail', order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)
    body = request.POST.get('body', '').strip()
    audio = request.FILES.get('audio')

    if not body and not audio:
        return redirect('kareem-request-detail', order_id=order_id)

    if not order.chat_open:
        messages.error(request, _('This chat is closed — the order was cancelled.'))
        return redirect('kareem-request-detail', order_id=order_id)

    try:
        validate_audio_upload(audio)
    except ValidationError:
        messages.error(request, _('Invalid audio recording.'))
        return redirect('kareem-request-detail', order_id=order_id)

    try:
        post_mechanic_message(order, body, audio=audio)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect('kareem-request-detail', order_id=order_id)
