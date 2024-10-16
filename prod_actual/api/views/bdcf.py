from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, IntegrityError
from django.db.models import Sum

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from prod_actual.models import ProductionRing, BoggedTonnes
from common.functions.common_methods import CommonMethods
from common.functions.shkey import Shkey

from datetime import timedelta, date

import json


class BoggingRingsView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_bogging_rings(request)
        return Response(rings, status=status.HTTP_200_OK)


class BoggingMovementsView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        bdcf = BDCFRings()
        movements = bdcf.get_bogging_movements(location_id)
        return Response(movements, status=status.HTTP_200_OK)


class DesignedRingsView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_designed_rings(request)
        return Response(rings, status=status.HTTP_200_OK)


class DrilledRingsView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_drilled_rings(request)
        return Response(rings, status=status.HTTP_200_OK)


class ChargedRingsView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_charged_rings(request)
        return Response(rings, status=status.HTTP_200_OK)


class BDCFRings():
    def __init__(self) -> None:
        pass

    def get_rings_status(self, level, status):
        pass

    def get_bogging_rings(self, request):
        current_rings = ProductionRing.objects.filter(
            status='Bogging').order_by('level', 'oredrive')
        dropdown_options = []

        # Iterate over the filtered rings
        for ring in current_rings:
            # Determine the concatenated value for multi_fire_group
            if ring.multi_fire_group != '(M)':
                if ring.multi_fire_group:
                    if ring.multi_fire_group == '(MP)':
                        ring_text = f"{ring.level}_{
                            ring.oredrive} R{ring.ring_number_txt}"
                    else:
                        ring_text = f"{ring.level}_{
                            ring.oredrive} {ring.multi_fire_group}"
                else:
                    ring_text = f"{ring.level}_{
                        ring.oredrive} R{ring.ring_number_txt}"

            # Append the formatted result with location_id
                dropdown_options.append({
                    'value': ring_text,
                    'location_id': ring.location_id
                })

        return dropdown_options

    def get_bogging_movements(self, location_id):
        # Filter BoggedTonnes by ProductionRing location_id
        bogged_entries = BoggedTonnes.objects.filter(
            production_ring__location_id=location_id)

        # Serialize the data as needed
        data = [
            {
                "tonnes": entry.bogged_tonnes,
                "date": Shkey.format_shkey_day_first(entry.shkey),
                "timestamp": entry.datetime_stamp,
                "user": {
                    "full_name": entry.entered_by.get_full_name() if entry.entered_by else "Mock User",
                    "avatar": "avatar-01.svg"
                } if entry.entered_by else None,
            }
            for entry in bogged_entries
        ]

        return data

    def get_designed_rings(self, request):
        pass

    def get_drilled_rings(self, request):
        pass

    def get_charged_rings(self, request):
        pass
