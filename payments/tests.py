import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Customer
from jobs.models import Conversation, Order
from payments.hmac import compute_transaction_hmac
from payments.models import Payment
from payments.services import (
    CALLBACK_AUTH_HOLD,
    CALLBACK_FAILED,
    CALLBACK_IGNORED,
    CALLBACK_PAID,
    CALLBACK_PENDING,
    CALLBACK_REFUNDED,
    CALLBACK_VOIDED,
    classify_paymob_callback,
)

HMAC_SECRET = 'test-paymob-hmac-secret'


def transaction_obj(order_id, txn_id='2556706', **overrides):
    obj = {
        'amount_cents': 10000,
        'created_at': '2020-03-25T18:39:44.719228',
        'currency': 'EGP',
        'error_occured': False,
        'has_parent_transaction': False,
        'id': txn_id,
        'integration_id': 6741,
        'is_3d_secure': True,
        'is_auth': False,
        'is_capture': False,
        'is_refunded': False,
        'is_standalone_payment': True,
        'is_voided': False,
        'order': {
            'id': 4778239,
            'merchant_order_id': str(order_id),
        },
        'owner': 4705,
        'pending': False,
        'source_data': {
            'pan': '2346',
            'sub_type': 'MasterCard',
            'type': 'card',
        },
        'success': True,
        'payment_key_claims': {'integration_id': '6741'},
    }
    obj.update(overrides)
    return obj


class ClassifyPaymobCallbackTests(TestCase):
    def test_standalone_success_is_paid(self):
        self.assertEqual(classify_paymob_callback(transaction_obj(1)), CALLBACK_PAID)

    def test_pending_is_not_failed(self):
        obj = transaction_obj(1, success=False, pending=True)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_PENDING)

    def test_success_still_pending_is_pending(self):
        obj = transaction_obj(1, success=True, pending=True)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_PENDING)

    def test_decline_is_failed(self):
        obj = transaction_obj(1, success=False, pending=False)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_FAILED)

    def test_refund_is_not_paid(self):
        obj = transaction_obj(1, is_refunded=True, has_parent_transaction=True)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_REFUNDED)

    def test_void_is_not_paid(self):
        obj = transaction_obj(1, is_voided=True, has_parent_transaction=True)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_VOIDED)

    def test_auth_without_capture_is_hold(self):
        obj = transaction_obj(1, is_auth=True, is_capture=False, is_standalone_payment=False)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_AUTH_HOLD)

    def test_capture_is_paid(self):
        obj = transaction_obj(1, is_auth=False, is_capture=True, is_standalone_payment=False)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_PAID)

    def test_success_with_error_is_ignored(self):
        obj = transaction_obj(1, success=True, error_occured=True)
        self.assertEqual(classify_paymob_callback(obj), CALLBACK_IGNORED)


@override_settings(PAYMOB_HMAC_SECRET=HMAC_SECRET)
class PaymobWebhookTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(phone='+201012345678')
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.QUOTED,
            quoted_price=Decimal('100.00'),
        )
        self.conversation = Conversation.objects.create(
            customer=self.customer,
            order=self.order,
        )
        self.pending = Payment.objects.create(
            order=self.order,
            amount_piasters=10000,
            status=Payment.Status.PENDING,
            paymob_intention_id='int-1',
        )
        self.url = reverse('paymob-webhook')

    def _post(self, obj, hmac_value=None, callback_type='TRANSACTION'):
        payload = {'type': callback_type, 'obj': obj}
        if hmac_value is None:
            hmac_value = compute_transaction_hmac(obj)
        return self.client.post(
            f'{self.url}?hmac={hmac_value}',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_invalid_hmac_is_rejected(self):
        obj = transaction_obj(self.order.pk)
        response = self._post(obj, hmac_value='deadbeef')
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.PENDING)

    def test_success_converts_pending_to_paid(self):
        obj = transaction_obj(self.order.pk, txn_id='txn-success-1')
        response = self._post(obj)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.PAID)
        self.assertEqual(self.pending.paymob_transaction_id, 'txn-success-1')
        self.assertTrue(
            self.conversation.messages.filter(body='__payment__').exists()
        )

    def test_success_is_idempotent_on_transaction_id(self):
        obj = transaction_obj(self.order.pk, txn_id='txn-same')
        self.assertEqual(self._post(obj).status_code, 200)
        self.assertEqual(self._post(obj).status_code, 200)
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)
        self.assertEqual(
            self.conversation.messages.filter(body='__payment__').count(),
            1,
        )

    def test_decline_marks_failed_and_stays_quoted(self):
        obj = transaction_obj(
            self.order.pk,
            txn_id='txn-fail-1',
            success=False,
            pending=False,
        )
        response = self._post(obj)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.FAILED)
        self.assertEqual(self.pending.paymob_transaction_id, 'txn-fail-1')
        self.assertTrue(
            self.conversation.messages.filter(body='__payment_failed__').exists()
        )

    def test_pending_does_not_mark_failed(self):
        obj = transaction_obj(
            self.order.pk,
            txn_id='txn-pending-1',
            success=False,
            pending=True,
        )
        response = self._post(obj)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.PENDING)
        self.assertFalse(
            self.conversation.messages.filter(body='__payment_failed__').exists()
        )

    def test_refund_is_acked_without_state_change(self):
        obj = transaction_obj(
            self.order.pk,
            txn_id='txn-refund-1',
            is_refunded=True,
            has_parent_transaction=True,
        )
        response = self._post(obj)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.PENDING)
        self.assertFalse(self.conversation.messages.exists())

    def test_void_is_acked_without_state_change(self):
        obj = transaction_obj(
            self.order.pk,
            txn_id='txn-void-1',
            is_voided=True,
            has_parent_transaction=True,
        )
        response = self._post(obj)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.PENDING)

    def test_token_callback_is_acked_without_hmac(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'type': 'TOKEN', 'obj': {'token': 'tok_abc'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Payment.Status.PENDING)

    def test_invalid_json_is_rejected(self):
        response = self.client.post(
            self.url,
            data='{not-json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
