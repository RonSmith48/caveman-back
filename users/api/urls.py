from django.urls import path
import users.api.views as v

urlpatterns = [
    path('activate/', v.ActivateUserView.as_view(), name='activate'),
    path('avatars/assign/', v.AssignAvatarView.as_view(), name='avatar-assign'),
    path('avatars/unassign/', v.UnassignAvatarView.as_view(), name='avatar-unassign'),
    path('avatars/list/', v.ListAvatarsView.as_view(), name='avatar-list'),
    path('avatars/flag/', v.FlagAvatarForDeleteView.as_view(),
         name='avatar-flag-delete'),
    path('avatars/sync/', v.AvatarSyncView.as_view(), name='avatar-sync'),
    path('login/', v.LoginView.as_view(), name='login'),
    path('register/', v.RegisterUserView.as_view(), name='register'),
    path('token-refresh/', v.CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('token-verify/', v.VerifyTokenView.as_view(), name='token_verify'),
    path('update/', v.UpdateProfileView.as_view(), name='update'),
    path('user/<int:id>', v.UserView.as_view(), name='user'),
]
