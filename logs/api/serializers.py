from rest_framework import serializers
from ..models import ErrorLog, WarningLog, UserActivityLog


class ErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorLog
        fields = '__all__'
        read_only_fields = ('timestamp',)


class WarningLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarningLog
        fields = '__all__'
        read_only_fields = ('timestamp',)


class UserActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivityLog
        fields = '__all__'
        read_only_fields = ('timestamp',)
