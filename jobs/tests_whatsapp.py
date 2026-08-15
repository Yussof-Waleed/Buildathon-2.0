from django.test import TestCase, override_settings
from django.urls import reverse

from jobs.whatsapp.phone import e164_from_wa_id, wa_id_from_e164


class WhatsAppPhoneTests(TestCase):
    def test_e164_from_digits(self):
        self.assertEqual(e164_from_wa_id('201012345678'), '+201012345678')

    def test_e164_strips_plus(self):
        self.assertEqual(e164_from_wa_id('+15551938692'), '+15551938692')

    def test_wa_id_from_e164(self):
        self.assertEqual(wa_id_from_e164('+201012345678'), '201012345678')


class WhatsAppCopyTests(TestCase):
    def test_quote_text_includes_pay_link_and_steps(self):
        from decimal import Decimal

        from accounts.models import Customer
        from jobs.models import Conversation, Order, OrderStep
        from jobs.whatsapp.copy import progress_whatsapp_text, quote_whatsapp_text

        customer = Customer.objects.create(phone='+201012345678')
        order = Order.objects.create(
            customer=customer,
            status=Order.Status.QUOTED,
            quoted_title_ar='تغيير زيت',
            quoted_title_en='Oil change',
            quoted_price=Decimal('250.00'),
        )
        Conversation.objects.create(customer=customer, order=order)
        OrderStep.objects.create(
            order=order,
            title_ar='فحص',
            title_en='Inspect',
            expected_minutes=20,
            sort_order=0,
        )
        text = quote_whatsapp_text(order, checkout_url='https://pay.example/checkout')
        self.assertIn('250', text)
        self.assertIn('https://pay.example/checkout', text)
        self.assertIn('فحص', text)

        order.status = Order.Status.IN_PROGRESS
        order.save(update_fields=['status'])
        progress = progress_whatsapp_text(order)
        self.assertIn('فحص', progress)
        self.assertNotIn('https://pay.example/checkout', progress)


class WhatsAppWebhookTests(TestCase):
    @override_settings(WHATSAPP_VERIFY_TOKEN='test-verify-token')
    def test_get_challenge_succeeds(self):
        url = reverse('whatsapp-webhook')
        response = self.client.get(
            url,
            {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'test-verify-token',
                'hub.challenge': 'challenge-123',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'challenge-123')

    @override_settings(WHATSAPP_VERIFY_TOKEN='test-verify-token')
    def test_get_challenge_rejects_bad_token(self):
        url = reverse('whatsapp-webhook')
        response = self.client.get(
            url,
            {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'wrong',
                'hub.challenge': 'challenge-123',
            },
        )
        self.assertEqual(response.status_code, 403)
