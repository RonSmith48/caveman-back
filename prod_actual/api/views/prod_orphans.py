from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from prod_actual.models import ProductionRing
from prod_concept.models import FlowModelConceptRing
from prod_actual.api.serializers import ProdRingSerializer

from settings.models import ProjectSetting
from report.models import JsonReport

from django.db.models import F, ExpressionWrapper, fields
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
                        Power(F('x') - orphan.x, 2) +
                        Power(F('y') - orphan.y, 2)
                    ),
                    output_field=fields.DecimalField(
                        max_digits=12, decimal_places=6)
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
            # Assuming 'value' is the JSONField where 'distValue' is stored
            dist_value = project_setting.value.get('distValue')
            self.threshold_dist = round(
                float(dist_value), 1) if dist_value else 2
        except ProjectSetting.DoesNotExist:
            self.threshold_dist = 2
            self.warning_msg = "Threshold not set, using default 2m"

    def store_orphan_count(self):
        # Fetch orphans without a concept_ring
        orphans = ProductionRing.objects.filter(concept_ring__isnull=True)
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
