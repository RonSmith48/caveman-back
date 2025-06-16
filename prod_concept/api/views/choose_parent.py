from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from prod_concept.models import FlowModelConceptRing
from prod_actual.models import ProductionRing


class ChooseParentView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        # 1) Fetch the orphan ring
        try:
            orphan = ProductionRing.objects.get(location_id=location_id)
        except ProductionRing.DoesNotExist:
            return Response(
                {"detail": f"Orphan ring {location_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        R = 20
        x_min, x_max = orphan.x - R, orphan.x + R
        y_min, y_max = orphan.y - R, orphan.y + R

        # 3) Query candidates on the same level, in that box, excluding the orphan itself
        candidates_qs = FlowModelConceptRing.objects.filter(
            is_active=True,
            level=orphan.level,
            x__gte=x_min, x__lte=x_max,
            y__gte=y_min, y__lte=y_max,
        ).exclude(location_id=location_id)

        nearby_rings_qs = ProductionRing.objects.filter(
            is_active=True,
            level=orphan.level,
            x__gte=x_min, x__lte=x_max,
            y__gte=y_min, y__lte=y_max,
        ).exclude(location_id=location_id)

        # 4) Serialize out the exact fields your UI needs
        candidates = []
        nearby_rings = []
        for ring in candidates_qs:
            candidates.append({
                "id":         ring.location_id,
                "name":       ring.blastsolids_id,
                "x":          float(ring.x),
                "y":          float(ring.y),
                "cu":         ring.modelled_cu,
                "au":         ring.modelled_au,
                "density":    ring.density,
            })

        for ring in nearby_rings_qs:
            nearby_rings.append({
                "id":         ring.location_id,
                "name":       ring.alias,
                "x":          float(ring.x),
                "y":          float(ring.y),
                "draw":       ring.draw_percentage,
                "parent": ring.concept_ring.blastsolids_id if ring.concept_ring else None,
            })

        data = {
            "orphan": {
                "id": orphan.location_id,
                "x":  float(orphan.x),
                "y":  float(orphan.y),
                "draw": orphan.draw_percentage,
                "parent": orphan.concept_ring.blastsolids_id if orphan.concept_ring else None,
            },
            "candidates": candidates,
            "nearby_rings": nearby_rings,
        }
        return Response(data, status=status.HTTP_200_OK)
