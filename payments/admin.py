from django.contrib import admin

from payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'amount_piasters',
        'status',
        'paymob_transaction_id',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('paymob_transaction_id', 'paymob_intention_id', 'order__id')
