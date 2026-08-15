import json

from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.customer_session import get_customer, require_customer
from jobs.models import Order
from payments.models import Payment
from payments.paymob import PaymobAPIError, PaymobNotConfiguredError, create_payment_intention
from payments.hmac import verify_transaction_hmac
from payments.services import (
    apply_failed_payment,
    apply_successful_payment,
    extract_order_id_from_callback,
)


@require_customer
@require_POST
def checkout(request, order_id):
    customer = get_customer(request)
    order = get_object_or_404(Order, pk=order_id, customer=customer)

    if order.status != Order.Status.QUOTED or order.quoted_price is None:
        messages.error(request, _('This order cannot be paid.'))
        return redirect('customer-order-detail', order_id=order.pk)

    try:
        checkout_url, intention_id = create_payment_intention(order)
    except PaymobNotConfiguredError as exc:
        messages.error(request, str(exc))
        return redirect('customer-order-detail', order_id=order.pk)
    except PaymobAPIError as exc:
        messages.error(request, _('Paymob error: %(detail)s') % {'detail': exc})
        return redirect('customer-order-detail', order_id=order.pk)

    amount_piasters = int(order.quoted_price * 100)
    pending = Payment.objects.filter(
        order=order,
        status=Payment.Status.PENDING,
    ).order_by('-created_at').first()

    if pending:
        pending.amount_piasters = amount_piasters
        pending.paymob_intention_id = intention_id
        pending.save()
    else:
        Payment.objects.create(
            order=order,
            amount_piasters=amount_piasters,
            status=Payment.Status.PENDING,
            paymob_intention_id=intention_id,
        )

    return redirect(checkout_url)


@csrf_exempt
@require_POST
def paymob_webhook(request):
    received_hmac = request.GET.get('hmac', '')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest('Invalid JSON')

    obj = payload.get('obj')
    if not obj:
        return HttpResponseBadRequest('Missing obj')

    if not verify_transaction_hmac(obj, received_hmac):
        return HttpResponseBadRequest('Invalid HMAC')

    order_id = extract_order_id_from_callback(obj)
    if order_id is None:
        return HttpResponseBadRequest('Missing order reference')

    transaction_id = str(obj.get('id', ''))
    if not transaction_id:
        return HttpResponseBadRequest('Missing transaction id')

    amount_piasters = int(obj.get('amount_cents') or 0)
    intention_id = str(obj.get('payment_key_claims', {}).get('integration_id', '') or '')

    success = obj.get('success') is True
    pending = obj.get('pending') is True

    if success and not pending:
        apply_successful_payment(
            order_id,
            transaction_id,
            amount_piasters,
            intention_id=intention_id,
        )
    elif not success:
        apply_failed_payment(
            order_id,
            transaction_id,
            amount_piasters,
            intention_id=intention_id,
        )

    return HttpResponse(status=200)
