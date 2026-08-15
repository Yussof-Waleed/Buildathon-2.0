from django.contrib import admin

from jobs.models import Conversation, Message, Order, OrderStep


class OrderStepInline(admin.TabularInline):
    model = OrderStep
    extra = 0
    fields = ('title', 'expected_minutes', 'sort_order', 'completed_at')
    readonly_fields = ('title', 'expected_minutes', 'sort_order')


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('author_type', 'body', 'channel', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'status',
        'quoted_price',
        'diagnostic',
        'created_at',
    )
    list_filter = ('status', 'labels')
    search_fields = ('customer__phone', 'kareem_note')
    filter_horizontal = ('labels',)
    inlines = [OrderStepInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'order', 'created_at')
    list_filter = ('customer',)
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'author_type', 'channel', 'created_at')
    list_filter = ('author_type', 'channel')
