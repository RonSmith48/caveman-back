from django.shortcuts import render
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.conf import settings
from django.db import DatabaseError, IntegrityError
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
from rest_framework.exceptions import AuthenticationFailed

from jwt.exceptions import ExpiredSignatureError

import random
import json
import logging

import users.api.serializers as s


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

            return Response({'msg': {'type': 'success', 'body': 'Profile updated successfully'}})

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

            # Optionally send OTP or handle other post-save actions
            err = self.send_otp_email(request, user.email)
            if err:
                logger.error("OTP sending error", exc_info=True, extra={
                    'user': user,
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                })
                return Response({'msg': {'type': 'error', 'body': 'There was an error sending your OTP'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                logger._log_user_activity("User registered", extra={
                    'user': user,
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'activity_type': 'user registered',
                })
                return Response({'msg': {'type': 'success', 'body': 'Registration successful'}, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        except IntegrityError:
            logger.error("Database integrity error - email address already taken", exc_info=True, extra={
                'user': request.user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
            })
            return Response({'msg': {'type': 'error', 'body': 'Email address already taken'}}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.error("Registration error", exc_info=True, extra={
                'user': request.user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Registration failed'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                    'user': request.user,
                    'url': request.build_absolute_uri(),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                })
                return Response({'msg': {'type': 'error', 'body': 'Unable to store OTP in database'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error("Unable to send OTP email", exc_info=True, extra={
                'user': request.user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Unable to send OTP email'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            return Response({'msg': {'type': 'error', 'body': serializer.errors}}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            # logged in serializer
            return Response({'msg': {'type': 'error', 'body': 'Invalid email'}}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error("Account activation failed", exc_info=True, extra={
                'user': request.user.id,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'stack_trace': e
            })
            return Response({'msg': {'type': 'error', 'body': 'Account activation failed'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

        except InvalidToken:
            # Handle invalid token case
            logger.user_activity("Invalid refresh token", extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': 'Invalid refresh token',
            })

            return Response({'msg': {'type': 'error', 'body': 'Invalid refresh token. Please try logging in again.'}},
                            status=status.HTTP_401_UNAUTHORIZED)

        except TokenError as e:
            # General token-related errors
            logger.error("Token refresh failed", exc_info=True, extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'error': str(e)
            })

            return Response({'msg': {'type': 'error', 'body': 'Token refresh failed. Please try again.'}},
                            status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Catch any other general exceptions
            logger.error("Unexpected error during token refresh", exc_info=True, extra={
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'error': str(e)
            })

            return Response({'msg': {'type': 'error', 'body': 'An unexpected error occurred.'}},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
