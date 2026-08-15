from django.urls import path

from payments import views

urlpatterns = [
    path(
        'orders/<int:order_id>/checkout/',
        views.checkout,
        name='api-checkout',
    ),
]
