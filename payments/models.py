from django.db import models

from jobs.models import Order


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    amount_piasters = models.PositiveIntegerField(
        help_text='Amount in piasters (10000 = 100.00 EGP)',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    paymob_intention_id = models.CharField(max_length=100, blank=True)
    paymob_transaction_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text='Paymob obj.id — unique for idempotent webhook handling',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment #{self.pk} — order #{self.order_id} ({self.status})'
