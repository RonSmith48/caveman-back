from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response

import prod_actual.api.serializers as s
import prod_actual.models as m


class LevelListView(APIView):
    def post(self, request):
        include_inactive = request.data.get('include_inactive', False)
        include_completed = request.data.get('include_completed', False)

        queryset = m.ProductionRing.objects.all()

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        levels = queryset.values_list(
            'level', flat=True).distinct().order_by('level')
        return Response(levels)


class OredriveListView(APIView):
    def post(self, request):
        level = request.data.get('level')
        include_inactive = request.data.get('include_inactive', False)
        include_completed = request.data.get('include_completed', False)

        if level is None:
            return Response([], status=400)

        queryset = m.ProductionRing.objects.filter(level=level)

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        oredrives = queryset.values_list(
            'oredrive', flat=True).distinct().order_by('oredrive')
        return Response(oredrives)


class RingNumberListView(APIView):
    def post(self, request):
        level = request.data.get('level')
        oredrive = request.data.get('oredrive')
        include_inactive = request.data.get('include_inactive', False)
        include_completed = request.data.get('include_completed', False)

        if not level or not oredrive:
            return Response([], status=400)

        queryset = m.ProductionRing.objects.filter(
            level=level, oredrive=oredrive)

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if not include_completed:
            queryset = queryset.exclude(status='Completed')

        # You can return full records or just the basics
        data = queryset.values(
            'location_id', 'ring_number_txt').order_by('ring_number_txt')
        return Response(data)
