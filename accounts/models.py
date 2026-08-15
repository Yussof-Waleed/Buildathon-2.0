from django.core.validators import RegexValidator
from django.db import models

E164_VALIDATOR = RegexValidator(
    regex=r'^\+[1-9]\d{1,14}$',
    message='Phone must be E.164 format (e.g. +201012345678).',
)


class Customer(models.Model):
    phone = models.CharField(
        max_length=16,
        unique=True,
        validators=[E164_VALIDATOR],
        help_text='E.164 format, e.g. +201012345678',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.phone
