"""
URL configuration for buildathon2 project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from jobs.views import home
from payments import views as payment_views
from payments.paymob_config import get_paymob_readiness


def health(_request):
    paymob = get_paymob_readiness()
    return JsonResponse({
        'status': 'ok',
        'product': 'warsha',
        'paymob': paymob,
    })


urlpatterns = [
    path('', home, name='home'),
    path('', include('jobs.urls')),
    path('k/', include('jobs.kareem_urls')),
    path('api/', include('payments.urls')),
    path('webhooks/paymob/', payment_views.paymob_webhook, name='paymob-webhook'),
    path('health/', health, name='health'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
