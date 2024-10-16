from rest_framework import generics
from prod_actual.models import ProductionRing
from rest_framework.response import Response
import prod_actual.api.serializers as s


class LevelListView(generics.ListAPIView):
    def get(self, request, *args, **kwargs):
        include_completed = request.query_params.get(
            'include_completed', 'false').lower() == 'true'

        queryset = ProductionRing.objects.all()
        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        levels = queryset.values_list('level', flat=True).distinct()
        return Response(levels)


class OredriveListView(generics.ListAPIView):
    def get(self, request, level, *args, **kwargs):
        include_completed = request.query_params.get(
            'include_completed', 'false').lower() == 'true'

        queryset = ProductionRing.objects.filter(level=level)
        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        oredrives = queryset.values_list('oredrive', flat=True).distinct()
        return Response(oredrives)


class RingNumberListView(generics.ListAPIView):
    def get(self, request, level, oredrive, *args, **kwargs):
        include_completed = request.query_params.get(
            'include_completed', 'false').lower() == 'true'

        queryset = ProductionRing.objects.filter(
            level=level, oredrive=oredrive)
        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        ring_numbers = queryset.values_list(
            'ring_number_txt', flat=True).distinct()
        return Response(ring_numbers)


class RingView(generics.RetrieveAPIView):
    serializer_class = s.ProdRingSerializer

    def get_object(self):
        level = self.kwargs['level']
        oredrive = self.kwargs['oredrive']
        ring_number_txt = self.kwargs['ring_number_txt']
        include_completed = self.request.query_params.get(
            'include_completed', 'false').lower() == 'true'

        queryset = ProductionRing.objects.filter(
            level=level, oredrive=oredrive, ring_number_txt=ring_number_txt)
        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        return queryset.first()
