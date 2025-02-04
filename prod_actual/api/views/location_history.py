from rest_framework.views import APIView
from rest_framework.response import Response

from prod_actual.models import ProductionRing


class LocationHistoryView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        print(request, location_id)
        return Response('Nice')
