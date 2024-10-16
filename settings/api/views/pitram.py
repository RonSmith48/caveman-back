from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

import settings.models as m
import settings.api.serializers as s


class PitramConnectionParamsView(APIView):
    """
    View to handle CRUD operations for Pitram connection parameters.
    """

    def post(self, request, *args, **kwargs):
        serializer = s.PitramConnectionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'msg': 'Database connection settings saved successfully'},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, key, *args, **kwargs):
        try:
            setting = m.ProjectSetting.objects.get(key=key)
            serializer = s.PitramConnectionSerializer(
                instance=setting, data=setting.value)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except m.ProjectSetting.DoesNotExist:
            return Response({'msg': 'Setting not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, key, *args, **kwargs):
        try:
            setting = m.ProjectSetting.objects.get(key=key)
            serializer = s.PitramConnectionSerializer(
                instance=setting, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {'msg': 'Database connection settings updated successfully'},
                    status=status.HTTP_200_OK
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except m.ProjectSetting.DoesNotExist:
            return Response({'msg': 'Setting not found'}, status=status.HTTP_404_NOT_FOUND)


class PitramConnectionTestView(APIView):
    """
    View to test database connection using provided connection details.
    """

    def post(self, request, *args, **kwargs):
        serializer = s.PitramConnectionSerializer(data=request.data)
        if serializer.is_valid():
            connection_details = serializer.validated_data

            # Build a database connection dictionary
            db_settings = self.build_db_settings(connection_details)

            try:
                # Create a temporary connection
                with connections['default'].temporary_connection() as temp_conn:
                    temp_conn.settings_dict.update(db_settings)
                    # Attempt to connect
                    temp_conn.ensure_connection()
                    if temp_conn.is_usable():
                        return Response({'msg': 'Connection successful'}, status=status.HTTP_200_OK)
                    else:
                        return Response({'msg': 'Connection failed'}, status=status.HTTP_400_BAD_REQUEST)
            except OperationalError as e:
                return Response({'msg': f'Connection failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def build_db_settings(self, connection_details):
        """
        Helper method to build the database settings dictionary.
        """
        return {
            'ENGINE': self.get_engine(connection_details['database_type']),
            'NAME': connection_details['database_name'],
            'USER': connection_details['username'],
            'PASSWORD': connection_details['password'],
            'HOST': connection_details['ip_address'],
            'PORT': connection_details['port'],
        }

    def get_engine(self, database_type):
        """
        Helper method to return the correct database engine string based on database type.
        """
        engines = {
            'sqlite': 'django.db.backends.sqlite3',
            'postgres': 'django.db.backends.postgresql',
            'sqlserver': 'sql_server.pyodbc',  # Corrected engine name for SQL Server
            'mysql': 'django.db.backends.mysql',
        }
        return engines.get(database_type.lower(), 'django.db.backends.sqlite3')
