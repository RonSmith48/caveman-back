from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

import settings.models as m
import settings.api.serializers as s


# List all settings or create a new one
class ProjectSettingListCreateView(generics.ListCreateAPIView):
    queryset = m.ProjectSetting.objects.all()
    serializer_class = s.ProjectSettingSerializer

# Retrieve, update or delete a setting by key


class ProjectSettingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = m.ProjectSetting.objects.all()
    serializer_class = s.ProjectSettingSerializer
    lookup_field = 'key'  # Use the 'key' field for lookups

    def get(self, request, *args, **kwargs):
        try:
            # Try to retrieve the setting by key
            return self.retrieve(request, *args, **kwargs)
        except NotFound:
            # If not found, return an empty JSON instead of raising a 404 error
            return JsonResponse({"key": self.kwargs.get('key'), "value": {}}, status=status.HTTP_200_OK)


'''
GET /api/settings/ — List all settings.
POST /api/settings/ — Create a new setting.
GET /api/settings/<key>/ — Retrieve a specific setting by key.
PUT /api/settings/<key>/ — Update a specific setting.
DELETE /api/settings/<key>/ — Delete a specific setting.
'''
