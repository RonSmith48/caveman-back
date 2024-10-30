from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import path, include

from whatif.api.views.drilling_scenario import UploadScheduleView

urlpatterns = [
    path('drilling/', UploadScheduleView.as_view(), name='drilling-scenario'),
]