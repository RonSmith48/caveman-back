from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from prod_actual.models import ProductionRing
from prod_concept.models import FlowModelConceptRing
from prod_actual.api.serializers import ProdRingSerializer

from settings.models import ProjectSetting
from report.models import JsonReport

from django.db.models import F, ExpressionWrapper, fields, Value
from django.db.models.functions import Power, Sqrt

from datetime import datetime, timedelta


class OrphanListView(generics.ListAPIView):
    serializer_class = ProdRingSerializer
    # Optionally specify a custom pagination class
    # pagination_class = YourPaginationClass

    def get_queryset(self):
        return ProductionRing.objects.filter(concept_ring__isnull=True)
        # return ProductionRing.objects.all()


class MatchProdConceptRingsView(APIView):
    def get(self, request):
        po = ProdOrphans()
        data = po.process_orphans()

        if "status_code" in data:
            return Response({data["msg"]}, status=data["status_code"])
        msg_body = f'{data["processed_count"]} rings processed, {
            data["matched"]} matched'
        return Response({"msg": {"body": msg_body, "type": "success"}, "orphan count": data["orphan count"]}, status=status.HTTP_200_OK)


class ProdOrphans():
    def __init__(self) -> None:
        self.threshold_dist = None
        self.error_msg = None
        self.warning_msg = None

        self.fetch_threshold_dist()

    def process_orphans(self):
        matches = 0
        orphans = ProductionRing.objects.filter(concept_ring__isnull=True)
        for orphan in orphans:
            # Find candidate FlowModelConceptRing with the same level
            candidates = FlowModelConceptRing.objects.filter(
                level=orphan.level)

            # Annotate candidates with the distance between their coordinates (x, y) and the orphan
            candidates = candidates.annotate(
                distance=ExpressionWrapper(
                    Sqrt(
                        (F('x') - Value(orphan.x)) * (F('x') - Value(orphan.x)) +
                        (F('y') - Value(orphan.y)) * (F('y') - Value(orphan.y))
                    ),
                    output_field=fields.DecimalField(max_digits=12, decimal_places=6)
                )
            )

            # Filter candidates based on threshold distance
            candidates = candidates.filter(distance__lte=self.threshold_dist)

            if candidates.exists():
                # Get the closest FlowModelConceptRing
                closest_ring = candidates.order_by('distance').first()

                if closest_ring.distance <= self.threshold_dist:
                    design_alias = str(orphan.level) + "_" + orphan.oredrive
                    matches += 1
                    orphan.concept_ring = closest_ring
                    orphan.save()
                    closest_ring.alias = design_alias
                    closest_ring.save()

        updated_orphans = self.store_orphan_count()

        if self.error_msg:
            return {"msg": {"type": "error", "body": self.error_msg}, "status_code": 500}
        return {"processed_count": orphans.count(), "matched": matches, "orphan count": updated_orphans["orphan count"]}

    def fetch_threshold_dist(self):
        try:
            project_setting = ProjectSetting.objects.get(key='ip_general')
            dist_value = project_setting.value.get('distValue', None)

            if dist_value is not None:
                self.threshold_dist = round(float(dist_value), 1)
            else:
                self.threshold_dist = 2
                self.warning_msg = "distValue not found in project setting; using default 2m"
        except (ProjectSetting.DoesNotExist, ValueError, TypeError) as e:
            self.threshold_dist = 2
            self.warning_msg = f"Could not fetch threshold; using default 2m. Error: {e}"


    def store_orphan_count(self):
        # Fetch orphans without a concept_ring
        orphans = ProductionRing.objects.filter(
            is_active=True, concept_ring__isnull=True)
        orphan_count = orphans.count()

        report_name = 'orphaned prod rings count'

        # Delete the existing report with the same name
        JsonReport.objects.filter(name=report_name).delete()

        # Create a new JsonReport entry
        JsonReport.objects.create(
            name=report_name,
            report={'orphan count': orphan_count}
        )
        return {'orphan count': orphan_count}

    def is_orphan(self, location_id):
        """
        Checks if a given location is orphaned.

        A location is considered orphaned if it has an active `ProductionRing` 
        entry where `concept_ring` is NULL (i.e., it is not linked to a conceptual ring).

        Args:
            location_id (int): The ID of the location to check.

        Returns:
            bool: True if the location is orphaned, False otherwise.

        Example:
            >>> is_orphan(123)
            True  # Location 123 is orphaned.

            >>> is_orphan(456)
            False  # Location 456 is linked to a conceptual ring.
        """
        return ProductionRing.objects.filter(
            is_active=True,
            concept_ring__isnull=True,
            location_id=location_id
        ).exists()
