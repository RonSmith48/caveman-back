from django.urls import path
from settings.api.views.pitram import PitramConnectionParamsView, PitramConnectionTestView
import settings.api.views.views as v


urlpatterns = [
    path('', v.ProjectSettingListCreateView.as_view(), name='setting-list-create'),
    path('pitram/connection/params', PitramConnectionParamsView.as_view(),
         name='pitram-connection-params'),
    path('pitram/connection/test', PitramConnectionTestView.as_view(),
         name='pitram-connection-test'),
    path('<str:key>/', v.ProjectSettingDetailView.as_view(), name='setting-detail'),
]

'''
GET /api/settings/ — List all settings.
POST /api/settings/ — Create a new setting.
GET /api/settings/<key>/ — Retrieve a specific setting by key.
PUT /api/settings/<key>/ — Update a specific setting.
DELETE /api/settings/<key>/ — Delete a specific setting.
'''
