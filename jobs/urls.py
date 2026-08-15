from django.urls import path

from jobs import views

urlpatterns = [
    path('chat/', views.customer_home, name='customer-chat'),
    path('chat/thread/', views.customer_chat_thread, name='customer-chat-thread'),
    path('orders/', views.customer_orders_list, name='customer-orders-list'),
    path('orders/<int:order_id>/', views.customer_order_detail, name='customer-order-detail'),
    path(
        'orders/<int:order_id>/thread/',
        views.customer_order_thread,
        name='customer-order-thread',
    ),
    path(
        'orders/<int:order_id>/cancel/',
        views.customer_order_cancel,
        name='customer-order-cancel',
    ),
]
