from django.shortcuts import render
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.base_user import BaseUserManager

from rest_framework import generics, status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from jwt.exceptions import ExpiredSignatureError

import random
import json
import logging

from users.api.avatar_colours import AvatarColours
import users.api.serializers as s
import users.models as m


User = get_user_model()
logger = logging.getLogger('custom_logger')


class UpdateProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            logger.warning("Un-authenticated attempt to update profile", exc_info=True, extra={
                'additional_info': request,
            })
            return Response({'msg': {'type': 'error', 'body': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = request.user  # The authenticated user
            serializer = s.UpdateUserProfileSerializer(
                user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.user_activity("User profile update", extra={
                'user': user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': f'{user.get_full_name()} updated their profile',
            })

            return Response({'msg': {'type': 'success', 'body': 'Profile updated successfully'}}, status=status.HTTP_200_OK)

        except DatabaseError:
            logger.error("Database error: Unable to update user profile", exc_info=True, extra={
                'user': request.user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
            })
            return Response({'msg': {'type': 'error', 'body': 'Database error: Unable to update user profile'}}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error("An error occurred", exc_info=True, extra={
                'user': request.user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Server error: Failed to update user profile'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterUserView(APIView):

    def post(self, request):
        try:
            serializer = s.RegisterUserSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            if not user.initials:
                user.initials = self.generate_initials(
                    user.first_name or '', user.last_name or '')

            bg, fg = AvatarColours.get_random_avatar_color()
            user.avatar = {
                "fg_colour": fg,
                "bg_colour": bg,
                "filename": None,
            }
            user.save()

            err = self.send_otp_email(request, user.email)
            if err:
                logger.error("OTP sending error", exc_info=True, extra={
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                })
                user.delete()

                if isinstance(err, dict) and 'msg' in err:
                    return Response(err, status=status.HTTP_200_OK)

                fallback_msg = {'msg': {
                    'type': 'error', 'body': 'We couldn’t send your OTP email. Please try again.'}}
                return Response(fallback_msg, status=status.HTTP_200_OK)

            logger.user_activity("User registered", extra={
                'user': user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'activity_type': 'user registered',
            })
            return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)

        except ValidationError as ve:
            # Check for specific known cases
            if 'email' in ve.detail and 'already exists' in str(ve.detail['email']):
                return Response({'msg': {'type': 'error', 'body': 'This email address is already registered.'}}, status=status.HTTP_200_OK)

            # Fallback to general validation message
            return Response({'msg': {'type': 'error', 'body': 'Invalid input. Please check the form and try again.'}}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("Unexpected registration error", exc_info=True, extra={
                'user': request.user if request.user.is_authenticated else None,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Something went wrong during registration'}}, status=status.HTTP_200_OK)

    def send_otp_email(self, request, email):
        subject = 'Your account verification email'
        otp = random.randint(1000, 9999)
        message_body = f'Your OTP is {otp}'
        try:
            email_from = 'caveman@evolutionmining.com'
            send_mail(subject, message_body, email_from, [email])

            try:
                user_obj = User.objects.get(email=email)
                user_obj.otp = otp
                user_obj.save()

                logger.user_activity("OTP email sent", extra={
                    'user': request.user,
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'description': f'OTP ({otp}) email sent to {email}',
                })
            except User.DoesNotExist:
                logger.error("User not found for OTP", exc_info=True, extra={
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                })
                print('Unable to store OTP in database')
                return {'msg': {'type': 'error', 'body': 'There is a database error'}}

        except Exception as e:
            logger.error("Unable to send OTP email", exc_info=True, extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            print('Unable to send OTP email')
            return {'msg': {'type': 'error', 'body': 'Mail server is not responding'}}

    def generate_initials(self, first_name, last_name):
        return f"{(first_name[:1] + last_name[:1]).upper()}" if first_name and last_name else "??"


class UserView(APIView):
    def get(self, request, id):
        try:
            user_obj = User.objects.get(id=id)
            serializer = s.UserSerializer(user_obj)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            logger.error("User not found", exc_info=True, extra={
                'user': request.user.id,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_id': id,
            })
            return Response({'msg': {'type': 'error', 'body': 'User not found'}}, status=status.HTTP_404_NOT_FOUND)

        except MultipleObjectsReturned:
            # This shouldn't be possible
            logger.error("Multiple users found with the same ID", exc_info=True, extra={
                'user': request.user.id,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_id': id,
            })
            return Response({'msg': {'type': 'error', 'body': 'Multiple users found with same ID'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error("Could not retrieve user", exc_info=True, extra={
                'user': request.user.id,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_id': id,
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Could not retrieve user'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ActivateUserView(APIView):
    def post(self, request):
        try:
            data = request.data
            serializer = s.VerifyAccountSerializer(data=data)

            if serializer.is_valid():
                user = User.objects.get(
                    email=serializer.validated_data['email'])
                user.is_active = True
                user.save()

                logger.user_activity("Account activated", extra={
                    'user': request.user.id,
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'description': 'Account activation successful',
                })

                return Response({'msg': {'type': 'success', 'body': 'Account activation successful'}}, status=status.HTTP_200_OK)

            # logged in serializer
            errors = serializer.errors
            error_str = '\n'.join(
                [f"{field}: {', '.join(messages)}" for field, messages in errors.items()])
            return Response({'msg': {'type': 'error', 'body': error_str}}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            # logged in serializer
            return Response({'msg': {'type': 'error', 'body': 'Invalid email'}}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("Account activation failed", exc_info=True, extra={
                'user': request.user.id,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Account activation failed'}}, status=status.HTTP_200_OK)


class LoginView(TokenObtainPairView):
    serializer_class = s.CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        print("authenticating user")
        serializer = self.get_serializer(data=request.data)
        try:

            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            logger.user_activity("login", extra={
                'user': data['user'].id,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': f'{data['user'].get_full_name()} logged in',
            })
            user_instance = data['user']
            serialized_user = s.UserSerializer(user_instance).data

            tokens = {'refresh': data['refresh'], 'access': data['access']}

            return Response({'tokens': tokens, 'user': serialized_user}, status=status.HTTP_200_OK)
        except AuthenticationFailed as e:
            # logged in serializer
            return Response({'msg': {'type': 'error', 'body': str(e)}}, status=status.HTTP_401_UNAUTHORIZED)


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        # Use the built-in TokenRefreshSerializer to handle the refresh process
        serializer = self.get_serializer(data=request.data)

        try:
            # Validate the refresh token
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            # Log user activity if needed (Optional)
            logger.user_activity("token_refresh", extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': 'User token refreshed successfully',
            })

            return Response(data, status=status.HTTP_200_OK)

        except ExpiredSignatureError:
            # Handle expired token case
            logger.user_activity("Refresh token expired", extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': 'Refresh token expired',
            })

            return Response({'msg': {'type': 'error', 'body': 'Refresh token has expired. Please log in again.'}},
                            status=status.HTTP_401_UNAUTHORIZED)

        except (TokenError, InvalidToken):
            # Handle invalid token case
            logger.user_activity("Invalid refresh token", extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': 'Invalid refresh token',
            })

            return Response({'msg': {'type': 'error', 'body': 'Invalid refresh token. Please try logging in again.'}},
                            status=status.HTTP_401_UNAUTHORIZED)

        except Exception as e:
            # Catch any other general exceptions
            logger.error("Unexpected error during token refresh", exc_info=True, extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'error': str(e)
            })

            return Response({'msg': {'type': 'error', 'body': 'An unexpected error occurred.'}},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyTokenView(APIView):
    """
    This endpoint checks if the provided access token is valid.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        If the request is authenticated, the token is valid.
        Otherwise, return a 401 error.
        """
        return Response({'msg': {'type': 'success', 'body': 'Token is valid'}}, status=status.HTTP_200_OK)


class AvatarSyncView(APIView):
    def post(self, request):
        incoming_filenames = request.data.get("filenames", [])

        if not isinstance(incoming_filenames, list):
            return Response({"detail": "Invalid data format."}, status=status.HTTP_400_BAD_REQUEST)

        existing_filenames = set(
            m.AvatarRegistry.objects.values_list("filename", flat=True)
        )
        incoming_set = set(incoming_filenames)

        # Add new filenames
        to_add = incoming_set - existing_filenames
        m.AvatarRegistry.objects.bulk_create([
            m.AvatarRegistry(filename=name) for name in to_add
        ])

        # Remove stale avatars (no longer in the avatar folder)
        to_remove = existing_filenames - incoming_set
        entries_to_remove = m.AvatarRegistry.objects.filter(
            filename__in=to_remove
        )

        # Forcefully unassign any user using these avatars
        for entry in entries_to_remove:
            if entry.assigned_to:
                user = entry.assigned_to
                user.avatar = None
                user.save()

        removed = list(entries_to_remove.values_list("filename", flat=True))
        entries_to_remove.delete()

        return Response({
            "added": list(to_add),
            "removed": removed,
            "unchanged": list(existing_filenames & incoming_set)
        }, status=status.HTTP_200_OK)


class ListAvatarsView(APIView):
    """
    GET /api/avatars/list/?filter=available|used|flagged|all
    Default is 'available' if no filter is provided.

    Usage Examples
    GET /api/avatars/list/ → shows available avatars (default)

    GET /api/avatars/list/?filter=used → shows in-use avatars

    GET /api/avatars/list/?filter=flagged → shows avatars flagged for deletion

    GET /api/avatars/list/?filter=all → shows everything

    """

    def get(self, request):
        filter_type = request.query_params.get('filter', 'available')

        if filter_type == 'available':
            avatars = m.AvatarRegistry.objects.filter(
                assigned_to__isnull=True,
                flag_for_delete=False
            )
        elif filter_type == 'used':
            avatars = m.AvatarRegistry.objects.filter(
                assigned_to__isnull=False)
        elif filter_type == 'flagged':
            avatars = m.AvatarRegistry.objects.filter(flag_for_delete=True)
        elif filter_type == 'all':
            avatars = m.AvatarRegistry.objects.all()
        else:
            return Response({"detail": "Invalid filter type."}, status=status.HTTP_400_BAD_REQUEST)

        result = [
            {
                "filename": avatar.filename,
                "assigned_to": avatar.assigned_to_id,
                "flag_for_delete": avatar.flag_for_delete,
            }
            for avatar in avatars
        ]
        return Response(result, status=status.HTTP_200_OK)


class AssignAvatarView(APIView):
    def post(self, request):
        user = request.user
        filename = request.data.get("filename")

        try:
            avatar_entry = m.AvatarRegistry.objects.get(
                filename=filename,
                assigned_to__isnull=True,
                flag_for_delete=False
            )
        except m.AvatarRegistry.DoesNotExist:
            return Response({"detail": "Avatar not available."}, status=status.HTTP_400_BAD_REQUEST)

        # Release previous avatar if it was assigned
        if user.registered_avatar:
            user.registered_avatar.assigned_to = None
            user.registered_avatar.save()

        # Assign new avatar
        user.avatar = {
            "filename": avatar_entry.filename,
            "bg_colour": "#ccc",  # Default or come from registry if stored there
        }
        user.save()

        avatar_entry.assigned_to = user
        avatar_entry.save()

        return Response({"detail": "Avatar assigned."}, status=status.HTTP_200_OK)


class UnassignAvatarView(APIView):
    def post(self, request):
        user = request.user
        avatar_entry = getattr(user, 'registered_avatar', None)

        if not avatar_entry:
            return Response({"detail": "No avatar to unassign."}, status=status.HTTP_400_BAD_REQUEST)

        # Always remove the avatar from the user
        user.avatar = None
        user.save()

        # Always mark it unassigned and not in use
        avatar_entry.assigned_to = None
        avatar_entry.save()

        return Response({"detail": "Avatar unassigned."}, status=status.HTTP_200_OK)


class FlagAvatarForDeleteView(APIView):
    def post(self, request):
        filename = request.data.get("filename")
        flag = request.data.get("flag", True)  # default to True

        try:
            avatar = m.AvatarRegistry.objects.get(filename=filename)
        except m.AvatarRegistry.DoesNotExist:
            return Response({"detail": "Avatar not found."}, status=status.HTTP_404_NOT_FOUND)

        avatar.flag_for_delete = flag
        avatar.save()
        return Response({"detail": f"Avatar {'flagged' if flag else 'unflagged'} for deletion."}, status=status.HTTP_200_OK)
