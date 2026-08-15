from accounts.customer_session import get_customer


def customer_session(request):
    return {'session_customer': get_customer(request)}
