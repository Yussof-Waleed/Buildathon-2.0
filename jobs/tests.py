from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.customer_session import SESSION_KEY
from accounts.models import Customer
from catalog.models import Diagnostic, Label
from jobs.models import Conversation, Message, Order
from jobs.services import post_mechanic_message, process_chat_message, start_order_work
from payments.models import Payment
from payments.services import apply_successful_payment


class CancelledChatLockTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(phone='+201012345678')
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.CANCELLED,
        )
        self.conversation = Conversation.objects.create(
            customer=self.customer,
            order=self.order,
        )

    def test_customer_cannot_post_on_cancelled_order(self):
        with self.assertRaises(ValidationError):
            process_chat_message(
                self.customer,
                'hello after cancel',
                conversation=self.conversation,
            )
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_mechanic_cannot_post_on_cancelled_order(self):
        with self.assertRaises(ValidationError):
            post_mechanic_message(self.order, 'reply after cancel')
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_customer_message_view_rejects_cancelled(self):
        session = self.client.session
        session[SESSION_KEY] = self.customer.pk
        session.save()
        response = self.client.post(
            reverse('customer-order-message', args=[self.order.pk]),
            {'body': 'still sending'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_kareem_message_view_rejects_cancelled(self):
        user_model = get_user_model()
        kareem = user_model.objects.create_user(
            username='kareem',
            password='warsha2026',
            is_staff=True,
        )
        self.client.force_login(kareem)
        response = self.client.post(
            reverse('kareem-request-message', args=[self.order.pk]),
            {'body': 'still sending'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conversation.messages.count(), 0)


def _voice_file():
    return SimpleUploadedFile('engine.ogg', b'ogg-bytes', content_type='audio/ogg')


@override_settings(GROQ_API_KEY='')
class IntakeRequiresTextAndAudioTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(phone='+201011112222')

    def test_text_only_does_not_create_order(self):
        result = process_chat_message(self.customer, 'المحرك بيعمل صوت')
        self.assertEqual(result.route, 'incomplete_intake')
        self.assertIsNone(result.order_id)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_audio_then_text_creates_order(self):
        first = process_chat_message(self.customer, '', audio=_voice_file())
        self.assertEqual(first.route, 'incomplete_intake')
        second = process_chat_message(self.customer, 'المحرك بيعمل صوت غريب')
        self.assertEqual(second.route, 'dumb_fallback')
        self.assertIsNotNone(second.order_id)

    def test_follow_up_on_bound_order_allows_text_only(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.IN_PROGRESS,
        )
        conversation = Conversation.objects.create(
            customer=self.customer,
            order=order,
        )
        result = process_chat_message(
            self.customer,
            'الخطوات ايه؟',
            conversation=conversation,
        )
        self.assertEqual(result.route, 'existing_order')
        self.assertEqual(result.order_id, order.pk)


class StartWorkAfterPaymentTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(phone='+201055512345')
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.QUOTED,
            quoted_price=Decimal('100.00'),
        )
        self.conversation = Conversation.objects.create(
            customer=self.customer,
            order=self.order,
        )
        user_model = get_user_model()
        self.kareem = user_model.objects.create_user(
            username='kareem-start',
            password='warsha2026',
            is_staff=True,
        )

    def test_successful_payment_marks_paid_not_in_progress(self):
        applied = apply_successful_payment(self.order.pk, 'txn-start-1', 10000)
        self.assertTrue(applied)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(
            Payment.objects.filter(
                order=self.order,
                status=Payment.Status.PAID,
            ).exists()
        )
        self.assertTrue(
            self.conversation.messages.filter(body='__payment__').exists()
        )
        self.assertFalse(
            self.conversation.messages.filter(body='__started__').exists()
        )

    def test_start_work_ignored_until_paid(self):
        start_order_work(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.QUOTED)

    def test_start_work_moves_paid_to_in_progress(self):
        apply_successful_payment(self.order.pk, 'txn-start-2', 10000)
        self.order.refresh_from_db()
        start_order_work(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.IN_PROGRESS)
        self.assertTrue(
            self.conversation.messages.filter(body='__started__').exists()
        )

    def test_kareem_start_work_view(self):
        apply_successful_payment(self.order.pk, 'txn-start-3', 10000)
        self.client.force_login(self.kareem)
        response = self.client.post(
            reverse('kareem-start-work', args=[self.order.pk]),
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.IN_PROGRESS)


@override_settings(GROQ_API_KEY='')
class TaggerBindAndQuoteTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(phone='+201099988877')
        self.engine_label = Label.objects.create(
            title_ar='ضوضاء المحرك',
            title_en='Engine noise',
        )
        self.engine = Diagnostic.objects.create(
            title_ar='إصلاح ضوضاء سير المحرك',
            title_en='Engine belt / noise repair',
            price=Decimal('950.00'),
        )
        self.brakes = Diagnostic.objects.create(
            title_ar='تغيير تيل الفرامل الأمامي',
            title_en='Front brake pads',
            price=Decimal('1400.00'),
        )
        user_model = get_user_model()
        self.kareem = user_model.objects.create_user(
            username='kareem-tagger',
            password='warsha2026',
            is_staff=True,
        )

    def test_bind_persists_labels_and_suggested_diagnostic(self):
        process_chat_message(self.customer, '', audio=_voice_file())
        result = process_chat_message(self.customer, 'المحرك بيعمل صوت غريب')
        self.assertEqual(result.route, 'dumb_fallback')
        order = Order.objects.get(pk=result.order_id)
        self.assertEqual(
            list(order.labels.values_list('pk', flat=True)),
            [self.engine_label.pk],
        )
        self.assertEqual(order.suggested_diagnostic_id, self.engine.pk)

    def test_quote_can_override_suggested_diagnostic(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PENDING_REVIEW,
            suggested_diagnostic=self.engine,
        )
        Conversation.objects.create(customer=self.customer, order=order)
        self.client.force_login(self.kareem)
        response = self.client.post(
            reverse('kareem-request-quote', args=[order.pk]),
            {'diagnostic_id': str(self.brakes.pk)},
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.QUOTED)
        self.assertEqual(order.diagnostic_id, self.brakes.pk)
        self.assertEqual(order.quoted_price, Decimal('1400.00'))
        self.assertEqual(order.suggested_diagnostic_id, self.engine.pk)

    def test_quote_form_preselects_suggestion(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PENDING_REVIEW,
            suggested_diagnostic=self.engine,
        )
        Conversation.objects.create(customer=self.customer, order=order)
        self.client.force_login(self.kareem)
        response = self.client.get(reverse('kareem-request-detail', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.engine.pk}"')
        self.assertContains(response, 'selected')
        self.assertContains(response, self.engine.title_ar)
