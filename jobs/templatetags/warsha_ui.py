from django import template
from django.urls import reverse
from django.utils.html import escape, format_html

register = template.Library()

STATUS_AR = {
    'pending_review': 'قيد المراجعة',
    'quoted': 'بانتظار الدفع',
    'in_progress': 'جاري الشغل',
    'ready_for_pickup': 'جاهزة للاستلام',
    'completed': 'تم الاستلام',
    'cancelled': 'ملغي',
}


@register.filter
def status_ar(status: str) -> str:
    return STATUS_AR.get(status, status)


@register.filter
def piasters_egp(piasters) -> str:
    if piasters is None:
        return '0.00'
    return f'{int(piasters) / 100:.2f}'


@register.filter
def chat_message_html(body: str):
    """Render [order:id] prefix as link to order detail."""
    if not body:
        return ''
    text = body.strip()
    if text.startswith('[order:') and ']' in text:
        bracket = text.index(']')
        order_part = text[7:bracket]
        try:
            order_id = int(order_part)
        except ValueError:
            return format_html('<span dir="auto">{}</span>', escape(text))
        rest = text[bracket + 1:].strip()
        url = reverse('customer-order-detail', args=[order_id])
        return format_html(
            '<span dir="auto">{}</span> <a href="{}" class="text-copper-bright no-underline">افتح الطلب</a>',
            escape(rest),
            url,
        )
    return format_html('<span dir="auto">{}</span>', escape(text))
