from django.urls import path
import users.api.views as v

urlpatterns = [
    path('activate/', v.ActivateUserView.as_view(), name='activate'),
    path('login/', v.LoginView.as_view(), name='login'),
    path('register/', v.RegisterUserView.as_view(), name='register'),
    path('token-refresh/', v.CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('token-verify/', v.VerifyTokenView.as_view(), name='token_verify'),
    path('update/', v.UpdateProfileView.as_view(), name='update'),
    path('user/<int:id>', v.UserView.as_view(), name='user'),
]
