# backend/common/authentication.py

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings

from django.contrib.auth import get_user_model
from users.utils import get_or_create_remote_user

import jwt, datetime
from django.utils import timezone

class JWTAuthenticationFetchUser(JWTAuthentication):
    """
    Custom JWTAuthentication that, if a token's user_id is not found in RemoteUser,
    will fetch from the Auth server and create the local row.
    """

    def get_user(self, validated_token, raw_token):
        """
        Attempt to return RemoteUser. If it doesn't exist locally, fetch & create it.
        """
        # By default, api_settings.USER_ID_CLAIM is 'user_id'
        user_id_claim = api_settings.USER_ID_CLAIM
        user_id = validated_token.get(user_id_claim)

        if user_id is None:
            raise AuthenticationFailed(
                'Token contained no user identification', 'invalid_token')

        # get UserModel (should be RemoteUser)
        UserModel = get_user_model()

        # Try the standard lookup. If not found, fetch from Auth server:
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            # Fetch‐and‐create logic:
            remote_user = get_or_create_remote_user(user_id, raw_token)
            if remote_user is None:
                # If the Auth server did not return a valid user, fail:
                raise AuthenticationFailed(
                    'User not found on Auth server', 'user_not_found')
            return remote_user

    def authenticate(self, request):
        """
        This is mostly identical to the parent method, except that
        get_user() now auto‐fetches if missing.
        """
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        # Now get_user() will auto-create if missing
        user = self.get_user(validated_token, raw_token)
        return (user, validated_token)
