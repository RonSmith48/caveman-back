from django.urls import path
import menu.api.views as v


urlpatterns = [
    path('', v.EmptyView.as_view(), name='empty-view'),
    path('dashboard/', v.UserDashboard.as_view(), name='user-dashboard'),
]
