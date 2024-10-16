from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/dev-actual/', include('dev_actual.api.urls')),
    path('api/dev-concept/', include('dev_concept.api.urls')),
    path('api/menu/', include('menu.api.urls')),
    path('api/prod-actual/', include('prod_actual.api.urls')),
    path('api/prod-concept/', include('prod_concept.api.urls')),
    path('api/logs/', include('logs.api.urls')),
    path('api/report/', include('report.api.urls')),
    path('api/settings/', include('settings.api.urls')),
    path('api/users/', include('users.api.urls')),
]
