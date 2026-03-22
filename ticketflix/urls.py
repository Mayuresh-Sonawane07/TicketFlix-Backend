from django.contrib import admin
from django.urls import path, include
from django.conf import settings
# from django.conf.urls.static import static

from django.views.static import serve
from django.urls import re_path

from django.http import JsonResponse
from django.core.files.storage import default_storage
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/events/', include('events.urls')),
    path('api/theaters/', include('theaters.urls')),
    path('api/bookings/', include('bookings.urls')),
    path('api/payments/', include('payments.urls')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path('debug/storage/', storage_debug),
]

def storage_debug(request):
    return JsonResponse({
        'storage_class': str(default_storage.__class__),
        'cloud_name': os.environ.get('CLOUD_NAME'),
        'api_key': os.environ.get('API_KEY'),
        'api_secret_set': bool(os.environ.get('API_SECRET')),
    })