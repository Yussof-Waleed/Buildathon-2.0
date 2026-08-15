from django.conf import settings
from django.utils.translation import gettext as _

from jobs.models import Order


def _status_label(order: Order) -> str:
    return str(order.get_status_display())


def _steps_block(order: Order) -> str:
    steps = list(order.steps.all())
    if not steps:
        return _('لا توجد خطوات مسجّلة على الطلب لسه.')

    lines = []
    for step in steps:
        mark = '✓' if step.completed_at else '○'
        lines.append(
            f'{mark} {step.localized_title} (~{step.expected_minutes} {_("دقيقة")})'
        )
    remaining = order.remaining_eta_minutes
    if remaining and order.status == Order.Status.IN_PROGRESS:
        lines.append(_('الوقت المتبقي تقريباً: %(minutes)s دقيقة.') % {
            'minutes': remaining,
        })
    return '\n'.join(lines)


def quote_whatsapp_text(order: Order, checkout_url: str | None = None) -> str:
    title = order.localized_quoted_title or _('صيانة')
    lines = [
        _('عرض سعر من ورشة كريم — طلب رقم %(id)s') % {'id': order.pk},
        '',
        title,
        f'{order.quoted_price} {_("جنيه")}',
        '',
        _('الخطوات:'),
        _steps_block(order),
    ]
    if order.kareem_note:
        lines.extend(['', _('ملاحظة كريم:'), order.kareem_note])
    if checkout_url:
        lines.extend(['', _('ادفع من هنا عشان نبدأ الشغل:'), checkout_url])
    else:
        lines.extend([
            '',
            _('ادفع من صفحة الطلب:'),
            f'{settings.SITE_URL}/orders/{order.pk}/',
        ])
    return '\n'.join(lines)


def progress_whatsapp_text(order: Order, checkout_url: str | None = None) -> str:
    lines = [
        _('طلب رقم %(id)s — %(status)s') % {
            'id': order.pk,
            'status': _status_label(order),
        },
        '',
        _('الخطوات:'),
        _steps_block(order),
    ]
    if order.status == Order.Status.QUOTED:
        if checkout_url:
            lines.extend(['', _('رابط الدفع:'), checkout_url])
        else:
            lines.extend([
                '',
                _('ادفع من صفحة الطلب:'),
                f'{settings.SITE_URL}/orders/{order.pk}/',
            ])
    elif order.status == Order.Status.READY_FOR_PICKUP:
        lines.extend(['', _('العربية جاهزة للاستلام — تقدر تيجي الورشة.')])
    elif order.status == Order.Status.PENDING_REVIEW:
        lines.extend(['', _('كريم لسه بيراجع الطلب وهيبعتم عرض السعر.')])
    return '\n'.join(lines)


def step_done_whatsapp_text(order: Order, step_title: str) -> str:
    return '\n'.join([
        _('تم إنجاز خطوة: %(title)s') % {'title': step_title},
        '',
        progress_whatsapp_text(order),
    ])


def ready_whatsapp_text(order: Order) -> str:
    return '\n'.join([
        _('العربية جاهزة للاستلام — تقدر تيجي الورشة. طلب رقم %(id)s') % {
            'id': order.pk,
        },
        '',
        _steps_block(order),
    ])


def paid_whatsapp_text(order: Order) -> str:
    return '\n'.join([
        _('تم تأكيد الدفع — بدأنا الشغل على طلب رقم %(id)s') % {'id': order.pk},
        '',
        _steps_block(order),
    ])
