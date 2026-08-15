from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.customer_session import SESSION_KEY
from accounts.models import Customer
from jobs.models import Conversation, Message, Order
from jobs.services import post_mechanic_message, process_chat_message


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
