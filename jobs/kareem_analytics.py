from django.db.models import Sum
from django.utils import timezone

from jobs.models import Order
from payments.models import Payment


def order_status_counts():
    return {
        status: Order.objects.filter(status=status).count()
        for status, _ in Order.Status.choices
    }


def payment_summary():
    today = timezone.localdate()
    week_start = today - timezone.timedelta(days=7)

    today_paid = Payment.objects.filter(
        status=Payment.Status.PAID,
        created_at__date=today,
    ).aggregate(total=Sum('amount_piasters'))['total'] or 0

    pending_count = Payment.objects.filter(status=Payment.Status.PENDING).count()

    failed_today = Payment.objects.filter(
        status=Payment.Status.FAILED,
        created_at__date=today,
    ).count()

    week_paid = Payment.objects.filter(
        status=Payment.Status.PAID,
        created_at__date__gte=week_start,
    ).aggregate(total=Sum('amount_piasters'))['total'] or 0

    return {
        'today_paid_piasters': today_paid,
        'week_paid_piasters': week_paid,
        'pending_count': pending_count,
        'failed_today': failed_today,
    }
