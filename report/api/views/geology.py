from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from prod_actual.models import ProductionRing
from prod_concept.models import FlowModelConceptRing
from prod_actual.api.serializers import ProdRingSerializer
from common.functions.shkey import Shkey

from settings.models import ProjectSetting
from report.models import JsonReport

from django.db.models import F, ExpressionWrapper, fields
from django.db.models.functions import Power, Sqrt

from datetime import datetime, timedelta


class FiredRingGradeView(APIView):
    def post(self, request, *args, **kwargs):
        gr = GeoReporting()
        date = request.data.get('date')
        rings = gr.get_fired_rings(date)

        return Response(rings, status=status.HTTP_200_OK)


class GeoReporting():
    def __init__(self):
        pass

    def get_fired_rings(self, date=None):

        if not date:
            date = datetime.now().date() - timedelta(days=1)

        shkey_day = Shkey.generate_shkey(date1=date, dn='d')
        shkey_night = Shkey.generate_shkey(date1=date, dn='n')

        rings = ProductionRing.objects.filter(
            fired_shift__in=[shkey_day, shkey_night])

        result = []
        for ring in rings:
            concept = ring.concept_ring
            shift_label = "Day" if ring.fired_shift == shkey_day else "Night"

            ring_info = {
                "alias": f"{ring.alias}",
                "density": concept.density if concept else None,
                "gold": concept.modelled_au if concept else None,
                "copper": concept.modelled_cu if concept else None,
                "shift": shift_label
            }
            result.append(ring_info)
            result.sort(key=lambda x: (
                0 if x["shift"] == "Day" else 1, x["alias"]))

        return result
