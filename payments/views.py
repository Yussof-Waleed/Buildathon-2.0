import json
import logging

from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.customer_session import get_customer, require_customer
from jobs.models import Order
from payments.hmac import verify_transaction_hmac
from payments.services import (
    CALLBACK_FAILED,
    CALLBACK_PAID,
    apply_failed_payment,
    apply_successful_payment,
    classify_paymob_callback,
    ensure_checkout_url,
    extract_order_id_from_callback,
)

logger = logging.getLogger(__name__)


@require_customer
@require_POST
def checkout(request, order_id):
    customer = get_customer(request)
    order = get_object_or_404(Order, pk=order_id, customer=customer)

    if order.status != Order.Status.QUOTED or order.quoted_price is None:
        messages.error(request, _('This order cannot be paid.'))
        return redirect('customer-order-detail', order_id=order.pk)

    checkout_url = ensure_checkout_url(order)
    if not checkout_url:
        messages.error(request, _('Paymob keys not configured.'))
        return redirect('customer-order-detail', order_id=order.pk)

    return redirect(checkout_url)


@csrf_exempt
@require_POST
def paymob_webhook(request):
    received_hmac = request.GET.get('hmac', '')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest('Invalid JSON')

    callback_type = payload.get('type')
    if callback_type and str(callback_type).upper() != 'TRANSACTION':
        logger.info('Ignoring non-transaction Paymob callback type=%s', callback_type)
        return HttpResponse(status=200)

    obj = payload.get('obj')
    if not isinstance(obj, dict) or not obj:
        return HttpResponseBadRequest('Missing obj')

    if not verify_transaction_hmac(obj, received_hmac):
        return HttpResponseBadRequest('Invalid HMAC')

    outcome = classify_paymob_callback(obj)
    transaction_id = str(obj.get('id', ''))

    if outcome not in (CALLBACK_PAID, CALLBACK_FAILED):
        logger.info(
            'Paymob callback acknowledged without state change: outcome=%s txn=%s',
            outcome,
            transaction_id,
        )
        return HttpResponse(status=200)

    if not transaction_id:
        return HttpResponseBadRequest('Missing transaction id')

    order_id = extract_order_id_from_callback(obj)
    if order_id is None:
        return HttpResponseBadRequest('Missing order reference')

    amount_piasters = int(obj.get('amount_cents') or 0)
    intention_id = str(obj.get('payment_key_claims', {}).get('integration_id', '') or '')

    if outcome == CALLBACK_PAID:
        apply_successful_payment(
            order_id,
            transaction_id,
            amount_piasters,
            intention_id=intention_id,
        )
    else:
        apply_failed_payment(
            order_id,
            transaction_id,
            amount_piasters,
            intention_id=intention_id,
        )

    return HttpResponse(status=200)
