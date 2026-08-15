"""Paymob HMAC-SHA-512 verification for Transaction Processed POST callbacks."""

import hashlib
import hmac

from django.conf import settings


def _field_to_str(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def verify_transaction_hmac(obj: dict, received_hmac: str) -> bool:
    """
    Verify POST webhook HMAC from body.obj.
    Field order per Paymob Transaction Processed callback spec.
    """
    if not received_hmac or not settings.PAYMOB_HMAC_SECRET:
        return False

    source_data = obj.get('source_data') or {}
    order = obj.get('order') or {}

    fields = [
        obj.get('amount_cents'),
        obj.get('created_at'),
        obj.get('currency'),
        obj.get('error_occured'),
        obj.get('has_parent_transaction'),
        obj.get('id'),
        obj.get('integration_id'),
        obj.get('is_3d_secure'),
        obj.get('is_auth'),
        obj.get('is_capture'),
        obj.get('is_refunded'),
        obj.get('is_standalone_payment'),
        obj.get('is_voided'),
        order.get('id'),
        obj.get('owner'),
        obj.get('pending'),
        source_data.get('pan'),
        source_data.get('sub_type'),
        source_data.get('type'),
        obj.get('success'),
    ]

    concat = ''.join(_field_to_str(field) for field in fields)
    computed = hmac.new(
        settings.PAYMOB_HMAC_SECRET.encode('utf-8'),
        concat.encode('utf-8'),
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(computed, received_hmac.lower())
