from django.urls import path
import logs.api.views as v

urlpatterns = [
    path('error-logs/', v.ErrorLogListCreateView.as_view(),
         name='error-log-list-create'),
    path('error-logs/<int:pk>/', v.ErrorLogDetailView.as_view(),
         name='error-log-detail'),

    path('warning-logs/', v.WarningLogListCreateView.as_view(),
         name='warning-log-list-create'),
    path('warning-logs/<int:pk>/', v.WarningLogDetailView.as_view(),
         name='warning-log-detail'),

    path('user-activity-logs/', v.UserActivityLogListCreateView.as_view(),
         name='user-activity-log-list-create'),
    path('user-activity-logs/<int:pk>/',
         v.UserActivityLogDetailView.as_view(), name='user-activity-log-detail'),
]
