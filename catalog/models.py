from django.db import models

from catalog.i18n import localized_field


class Label(models.Model):
    title_ar = models.CharField(max_length=100, unique=True)
    title_en = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title_ar']

    def __str__(self):
        return self.localized_title

    @property
    def localized_title(self) -> str:
        return localized_field(self, 'title')


class Diagnostic(models.Model):
    title_ar = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price in EGP')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title_ar']

    def __str__(self):
        return f'{self.localized_title} ({self.price} EGP)'

    @property
    def localized_title(self) -> str:
        return localized_field(self, 'title')


class DiagnosticStep(models.Model):
    diagnostic = models.ForeignKey(
        Diagnostic,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    title_ar = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200)
    description_ar = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    expected_minutes = models.PositiveIntegerField(default=30)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.localized_title

    @property
    def localized_title(self) -> str:
        return localized_field(self, 'title')

    @property
    def localized_description(self) -> str:
        return localized_field(self, 'description')
