import re
from functools import wraps

from django.shortcuts import redirect

from accounts.models import Customer, E164_VALIDATOR

SESSION_KEY = 'customer_id'


def normalize_phone(raw: str) -> str:
    """Normalize Egyptian local numbers to E.164 (+20…)."""
    phone = re.sub(r'\s+', '', raw.strip())
    if phone.startswith('00'):
        phone = '+' + phone[2:]
    elif phone.startswith('0'):
        phone = '+20' + phone[1:]
    elif not phone.startswith('+'):
        phone = '+20' + phone
    E164_VALIDATOR(phone)
    return phone


def get_customer(request) -> Customer | None:
    customer_id = request.session.get(SESSION_KEY)
    if not customer_id:
        return None
    return Customer.objects.filter(pk=customer_id).first()


def login_customer(request, raw_phone: str) -> Customer:
    phone = normalize_phone(raw_phone)
    customer, _ = Customer.objects.get_or_create(phone=phone)
    request.session[SESSION_KEY] = customer.pk
    return customer


def require_customer(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if get_customer(request) is None:
            return redirect('customer-chat')
        return view_func(request, *args, **kwargs)

    return wrapper
