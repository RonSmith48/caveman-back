from rest_framework import generics, status
from rest_framework.response import Response


class EmptyView(generics.ListAPIView):
    def get(self, request, *args, **kwargs):
        return Response({'msg': {'type': 'error', 'body': 'code not implemented'}}, status=status.HTTP_501_NOT_IMPLEMENTED)


class UserDashboard(generics.ListAPIView):
    def get(self, request, *args, **kwargs):
        print("dashboard requested")
        return Response({'msg': {'type': 'error', 'body': 'code not implemented'}}, status=status.HTTP_501_NOT_IMPLEMENTED)
