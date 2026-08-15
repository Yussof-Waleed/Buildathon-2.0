"""Paymob Intention API client."""

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from django.conf import settings

from jobs.services import piasters_from_egp
from payments.paymob_config import get_paymob_readiness


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


class PaymobNotConfiguredError(Exception):
    """Paymob env vars missing."""


class PaymobAPIError(Exception):
    """Paymob API returned an error."""


PAYMOB_BASE_URL = 'https://accept.paymob.com'


def _is_configured() -> bool:
    return get_paymob_readiness()['ready']


def build_redirection_url(order_id: int) -> str:
    if settings.PAYMOB_REDIRECTION_URL:
        return settings.PAYMOB_REDIRECTION_URL.replace('{order_id}', str(order_id))
    return f'{settings.SITE_URL}/orders/{order_id}/?paid=return'


def create_payment_intention(order) -> tuple[str, str]:
    """
    Create a Paymob payment intention and return (checkout_url, intention_id).
    """
    if not _is_configured():
        raise PaymobNotConfiguredError(
            'Paymob keys not configured. Set PAYMOB_SECRET_KEY, PAYMOB_PUBLIC_KEY, '
            'and PAYMOB_INTEGRATION_ID_CARD in .env'
        )

    amount = piasters_from_egp(order.quoted_price)
    phone = order.customer.phone
    if order.quoted_title_en:
        item_name = order.quoted_title_en
    elif order.diagnostic_id:
        item_name = order.diagnostic.title_en
    else:
        item_name = f'Order {order.pk}'

    payload = {
        'amount': amount,
        'currency': 'EGP',
        'payment_methods': [int(settings.PAYMOB_INTEGRATION_ID_CARD)],
        'items': [
            {
                'name': item_name,
                'amount': amount,
                'quantity': 1,
            },
        ],
        'billing_data': {
            'first_name': 'Customer',
            'last_name': 'Warsha',
            'phone_number': phone,
            'email': 'customer@warsha.local',
            'street': 'NA',
            'building': 'NA',
            'floor': 'NA',
            'apartment': 'NA',
            'city': 'Cairo',
            'country': 'EGY',
            'state': 'Cairo',
        },
        'special_reference': str(order.pk),
        'notification_url': settings.PAYMOB_NOTIFICATION_URL,
        'redirection_url': build_redirection_url(order.pk),
    }

    request = Request(
        f'{PAYMOB_BASE_URL}/v1/intention/',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Token {settings.PAYMOB_SECRET_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=30, context=_ssl_context()) as response:
            data = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        error_body = exc.read().decode('utf-8', errors='replace')
        raise PaymobAPIError(f'Paymob HTTP {exc.code}: {error_body}') from exc
    except URLError as exc:
        raise PaymobAPIError(f'Paymob connection error: {exc.reason}') from exc

    client_secret = data.get('client_secret')
    intention_id = str(data.get('id', ''))

    if not client_secret:
        raise PaymobAPIError(f'Paymob response missing client_secret: {data}')

    checkout_url = (
        f'{PAYMOB_BASE_URL}/unifiedcheckout/'
        f'?publicKey={settings.PAYMOB_PUBLIC_KEY}'
        f'&clientSecret={client_secret}'
    )
    return checkout_url, intention_id
