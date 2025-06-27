from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

import users.models as m
import logging

logger = logging.getLogger('custom_logger')


class UpdateUserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = m.RemoteUser
        fields = ['first_name', 'last_name',
                  'initials', 'role', 'avatar', 'full_name']

    def validate_first_name(self, value):
        return value.capitalize()

    def validate_last_name(self, value):
        return value.capitalize()

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get(
            'first_name', instance.first_name)
        instance.last_name = validated_data.get(
            'last_name', instance.last_name)
        instance.initials = validated_data.get('initials', instance.initials)
        instance.role = validated_data.get('role', instance.role)

        # Handle avatar safely for MSSQL
        avatar = validated_data.get('avatar', instance.avatar)
        if 'avatar' == "":
            instance.avatar = None
        else:
            instance.avatar = avatar

        instance.save()
        return instance


class RegisterUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.RemoteUser
        fields = ['email', 'first_name', 'last_name',
                  'password', 'initials', 'role']
        extra_kwargs = {
            'password': {'write_only': True},
            # allow blank in registration form, but still included
            'initials': {'required': False}
        }

    def validate_first_name(self, value):
        return value.capitalize()

    def validate_last_name(self, value):
        return value.capitalize()

    def create(self, validated_data):
        password = validated_data.pop('password')
        initials = validated_data.get('initials')
        if not initials:
            initials = f"{validated_data['first_name'][0]}{validated_data['last_name'][0]}".upper(
            )
        validated_data['initials'] = initials
        user = m.RemoteUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = m.RemoteUser
        exclude = ['password']  # Exclude sensitive fields

    def get_full_name(self, obj):
        return obj.get_full_name()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        credentials = {
            'email': attrs.get('email'),
            'password': attrs.get('password')
        }

        user = authenticate(**credentials)

        if user:
            if not user.is_active:
                logger.warning("Account is not activated", exc_info=True, extra={
                    'additional_info': credentials.email,
                    'url': 'login',
                })
                raise AuthenticationFailed('Account is not activated')

            refresh = self.get_token(user)
            data = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': user,
            }

            return data
        else:
            logger.warning("User not registered", exc_info=True, extra={
                'additional_info': credentials,
                'url': 'login',
            })
            raise AuthenticationFailed('User not registered')


class VerifyAccountSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        email = data.get('email')
        otp = data.get('otp')

        try:
            user = m.RemoteUser.objects.get(email=email)
        except m.RemoteUser.DoesNotExist:
            logger.warning("Invalid email entered", exc_info=True, extra={
                'additional_info': email,
                'url': 'verify account',
            })
            raise serializers.ValidationError(
                "Invalid email or user does not exist.")

        if user.otp != otp:
            logger.warning("Incorrect OTP entered", exc_info=True, extra={
                'user': user,
                'additional_info': email,
                'url': 'verify account',
            })
            raise serializers.ValidationError("Incorrect OTP.")

        if user.is_active:
            logger.warning("User account is already active", exc_info=True, extra={
                'url': 'verify account',
                'user': user,
            })
            raise serializers.ValidationError(
                "User account is already active.")

        return data
