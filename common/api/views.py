from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response


class ExportableTablesView(APIView):
    """
    View to handle exportable tables.
    """

    def get(self, request, *args, **kwargs):
        print("ExportableTablesView GET method called")
        # Logic to export tables
        return Response({"message": "Exportable tables"})
