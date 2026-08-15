from django.urls import path

from catalog.kareem_views import (
    kareem_diagnostic_create,
    kareem_diagnostic_delete,
    kareem_diagnostic_edit,
    kareem_diagnostics_list,
    kareem_label_delete,
    kareem_label_edit,
    kareem_labels_list,
)
from jobs.kareem_views import (
    KareemLoginView,
    KareemLogoutView,
    kareem_complete_step,
    kareem_confirm_paid,
    kareem_mark_completed,
    kareem_mark_ready,
    kareem_money,
    kareem_overview,
    kareem_request_detail,
    kareem_request_message,
    kareem_request_quote,
    kareem_request_thread,
    kareem_requests_list,
)

urlpatterns = [
    path('login/', KareemLoginView.as_view(), name='kareem-login'),
    path('logout/', KareemLogoutView.as_view(), name='kareem-logout'),
    path('', kareem_overview, name='kareem-overview'),
    path('requests/', kareem_requests_list, name='kareem-requests-list'),
    path('money/', kareem_money, name='kareem-money'),
    path('diagnostics/', kareem_diagnostics_list, name='kareem-diagnostics-list'),
    path('diagnostics/new/', kareem_diagnostic_create, name='kareem-diagnostic-create'),
    path(
        'diagnostics/<int:diagnostic_id>/edit/',
        kareem_diagnostic_edit,
        name='kareem-diagnostic-edit',
    ),
    path(
        'diagnostics/<int:diagnostic_id>/delete/',
        kareem_diagnostic_delete,
        name='kareem-diagnostic-delete',
    ),
    path('labels/', kareem_labels_list, name='kareem-labels-list'),
    path('labels/<int:label_id>/edit/', kareem_label_edit, name='kareem-label-edit'),
    path('labels/<int:label_id>/delete/', kareem_label_delete, name='kareem-label-delete'),
    path('requests/<int:order_id>/', kareem_request_detail, name='kareem-request-detail'),
    path(
        'requests/<int:order_id>/message/',
        kareem_request_message,
        name='kareem-request-message',
    ),
    path(
        'requests/<int:order_id>/thread/',
        kareem_request_thread,
        name='kareem-request-thread',
    ),
    path(
        'requests/<int:order_id>/quote/',
        kareem_request_quote,
        name='kareem-request-quote',
    ),
    path(
        'requests/<int:order_id>/confirm-paid/',
        kareem_confirm_paid,
        name='kareem-confirm-paid',
    ),
    path(
        'requests/<int:order_id>/mark-ready/',
        kareem_mark_ready,
        name='kareem-mark-ready',
    ),
    path(
        'requests/<int:order_id>/mark-completed/',
        kareem_mark_completed,
        name='kareem-mark-completed',
    ),
    path(
        'requests/<int:order_id>/steps/<int:step_id>/complete/',
        kareem_complete_step,
        name='kareem-complete-step',
    ),
]
