from django.db import models

from accounts.models import Customer
from catalog.models import Diagnostic, Label


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = 'pending_review', 'Pending review'
        QUOTED = 'quoted', 'Quoted'
        IN_PROGRESS = 'in_progress', 'In progress'
        READY_FOR_PICKUP = 'ready_for_pickup', 'Ready for pickup'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
        db_index=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    labels = models.ManyToManyField(Label, blank=True, related_name='orders')
    diagnostic = models.ForeignKey(
        Diagnostic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        help_text='Source template used at quote time',
    )
    quoted_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Snapshotted EGP price at quote time',
    )
    kareem_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order #{self.pk} — {self.customer.phone} ({self.status})'

    @property
    def remaining_eta_minutes(self) -> int:
        return sum(
            step.expected_minutes
            for step in self.steps.filter(completed_at__isnull=True)
        )

    @property
    def progress_percent(self) -> int:
        total = self.steps.count()
        if total == 0:
            return 0
        done = self.steps.filter(completed_at__isnull=False).count()
        return round(done * 100 / total)


class OrderStep(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    expected_minutes = models.PositiveIntegerField(default=30)
    sort_order = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title


class Conversation(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.order_id:
            return f'Conversation for order #{self.order_id}'
        return f'Intake conversation — {self.customer.phone}'


class Message(models.Model):
    class AuthorType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        MECHANIC = 'mechanic', 'Mechanic'
        SYSTEM = 'system', 'System'

    class Channel(models.TextChoices):
        WEB = 'web', 'Web'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    author_type = models.CharField(max_length=10, choices=AuthorType.choices)
    body = models.TextField(blank=True)
    audio = models.FileField(upload_to='messages/audio/', blank=True, null=True)
    channel = models.CharField(
        max_length=10,
        choices=Channel.choices,
        default=Channel.WEB,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        preview = (self.body or 'audio')[:40]
        return f'{self.author_type}: {preview}'
