def e164_from_wa_id(wa_id: str) -> str:
    """Map a WhatsApp wa_id (digits, no plus) to the Customer E.164 field."""
    digits = ''.join(ch for ch in str(wa_id) if ch.isdigit())
    if not digits:
        raise ValueError('WhatsApp wa_id has no digits')
    return f'+{digits}'


def wa_id_from_e164(phone: str) -> str:
    """WhatsApp Cloud API recipient id is digits only."""
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    if not digits:
        raise ValueError('Phone has no digits')
    return digits
