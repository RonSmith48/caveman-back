from rest_framework import generics
from ..models import ErrorLog, WarningLog, UserActivityLog
from .serializers import ErrorLogSerializer, WarningLogSerializer, UserActivityLogSerializer


class ErrorLogListCreateView(generics.ListCreateAPIView):
    queryset = ErrorLog.objects.all()
    serializer_class = ErrorLogSerializer


class ErrorLogDetailView(generics.RetrieveDestroyAPIView):
    queryset = ErrorLog.objects.all()
    serializer_class = ErrorLogSerializer


class WarningLogListCreateView(generics.ListCreateAPIView):
    queryset = WarningLog.objects.all()
    serializer_class = WarningLogSerializer


class WarningLogDetailView(generics.RetrieveDestroyAPIView):
    queryset = WarningLog.objects.all()
    serializer_class = WarningLogSerializer


class UserActivityLogListCreateView(generics.ListCreateAPIView):
    queryset = UserActivityLog.objects.all()
    serializer_class = UserActivityLogSerializer


class UserActivityLogDetailView(generics.RetrieveDestroyAPIView):
    queryset = UserActivityLog.objects.all()
    serializer_class = UserActivityLogSerializer
