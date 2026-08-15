from django.contrib import admin

from accounts.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('phone', 'created_at')
    search_fields = ('phone',)
