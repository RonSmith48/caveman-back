from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from common.functions.shkey import Shkey

from datetime import datetime, timedelta

import prod_actual.models as pm


class DCFReportView(APIView):
    def post(self, request, *args, **kwargs):
        pr = ProdReporting()
        date = request.data.get('date')
        rings = pr.get_dcf_rings(date)

        return Response(rings, status=status.HTTP_200_OK)


class BogVerifyReportView(APIView):
    def post(self, request, *args, **kwargs):
        pr = ProdReporting()
        data = request.data
        tonnes = pr.get_bog_tonnes_shift(data)

        return Response(tonnes, status=status.HTTP_200_OK)


class ProdReporting():
    def __init__(self):
        pass

    def get_dcf_rings(self, date=None):
        if not date:
            date = datetime.now().date() - timedelta(days=1)

        shkey_day = Shkey.generate_shkey(date1=date, dn='d')
        shkey_night = Shkey.generate_shkey(date1=date, dn='n')
        shkeys = [shkey_day, shkey_night]

        shift_map = {shkey_day: 'Day', shkey_night: 'Night'}

        # Fetch all rings that had *any* activity on this date
        rings = pm.ProductionRing.objects.filter(
            Q(drill_complete_shift__in=shkeys) |
            Q(charge_shift__in=shkeys) |
            Q(fired_shift__in=shkeys)
        )

        result = []

        for ring in rings:
            if ring.drill_complete_shift in shkeys:
                result.append({
                    "alias": ring.alias,
                    "status": ring.status,
                    "shift": shift_map[ring.drill_complete_shift],
                    "activity": "Drilled"
                })
            if ring.charge_shift in shkeys:
                result.append({
                    "alias": ring.alias,
                    "status": ring.status,
                    "shift": shift_map[ring.charge_shift],
                    "activity": "Charged"
                })
            if ring.fired_shift in shkeys:
                result.append({
                    "alias": ring.alias,
                    "status": ring.status,
                    "shift": shift_map[ring.fired_shift],
                    "activity": "Fired"
                })

        # Sort by shift (Day before Night), then activity
        result.sort(key=lambda x: (
            0 if x["shift"] == "Day" else 1, x["activity"], x["alias"]))

        return result

    def get_bog_tonnes_shift(self, data):
        date = data.get('date')
        shift = data.get('shift')
        shkey = Shkey.generate_shkey(date, shift)

        bogged_entries = pm.BoggedTonnes.objects.select_related(
            'production_ring').filter(shkey=shkey)

        results = [
            {
                'alias': entry.production_ring.alias,
                'quantity': float(entry.bogged_tonnes)
            }
            for entry in bogged_entries
        ]

        return results
