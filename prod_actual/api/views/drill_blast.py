from prod_actual import models as m
from datetime import date
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

import prod_actual.models as m
import prod_concept.models as cm
import prod_actual.api.serializers as s
import csv
import io
import json

from settings.models import ProjectSetting
from report.models import JsonReport

from django.db.models import F, ExpressionWrapper, fields, Value
from django.db.models.functions import Power, Sqrt

from datetime import datetime, timedelta, date
from decimal import Decimal

import logging
logger = logging.getLogger(__name__)


class OrphanListView(generics.ListAPIView):
    serializer_class = s.ProdRingSerializer
    # Optionally specify a custom pagination class
    # pagination_class = YourPaginationClass

    def get_queryset(self):
        return m.ProductionRing.objects.filter(concept_ring__isnull=True)


class MatchProdConceptRingsView(APIView):
    def get(self, request):
        po = ProdOrphans()
        data = po.process_orphans()

        if "status_code" in data:
            return Response({data["msg"]}, status=data["status_code"])
        msg_body = f'{data["processed_count"]} rings processed, {
            data["matched"]} matched'
        return Response({"msg": {"body": msg_body, "type": "success"}}, status=status.HTTP_200_OK)


class DesignedRingsView(APIView):
    def get(self, request):
        rings = m.ProductionRing.objects.filter(
            concept_ring__isnull=False,
            status='Designed',
        ).order_by('level', 'oredrive', 'ring_number_txt')

        serializer = s.ProductionRingReportSerializer(rings, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class RingDesignUploadView(APIView):
    def post(self, request):
        ring_file = request.FILES.get('ring_file')
        hole_file = request.FILES.get('hole_file')

        try:
            service = RingDesignService()
            service.upload_design(ring_file, hole_file)
            msg = {
                'msg': {'body': 'Ring data processed successfully', 'type': 'success'}}
            return Response(msg, status=status.HTTP_200_OK)
        except ValueError as ve:
            msg = {'msg': {'body': str(ve), 'type': 'error'}}
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            msg = {'msg': {
                'body': 'Unexpected error while processing ring design', 'type': 'error'}}
            return Response(msg, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RingDesignService:
    HOLE_DATA_HEADERS = [
        'RingID', 'HoleID', 'Length', 'Total Length', 'Dip', 'Dump', 'BT', 'Uphole',
        'Offset', 'CollarOffset', 'CollarOffset Vertical', 'Diameter',
        'CollarX', 'CollarY', 'CollarZ', 'ToeX', 'ToeY', 'ToeZ',
        'Pivot', 'PivotHeight', 'PivotHeightVertical',
        'NoOfRods', 'NoOfRodsReal', 'TrueAzimuth', 'TrueDip',
        'Offset to left wall', 'Offset to right wall',
        'Distance to left wall marker', 'Distance to right wall marker',
        'Dump direction', 'Distance from left wall to pivot', 'Distance from right wall to pivot',
        'Toe space to next', 'Toe space to previous', 'Length from pivot to toe'
    ]

    def __init__(self):
        self.ring_map = {}

    def upload_design(self, ring_file, hole_file):
        if not ring_file or not hole_file:
            raise ValueError("Both ring_file and hole_file are required.")

        self.process_ring_file(ring_file)
        self.attach_hole_data(hole_file)

    def process_ring_file(self, ring_file):
        try:
            decoded_file = ring_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded_file))

            for row in reader:
                config_raw = row.get('Configuration', '').strip()
                if len(config_raw) < 5 or '_' not in config_raw:
                    logger.warning(f"Invalid Configuration: {config_raw}")
                    continue

                level_str = config_raw[:4]
                oredrive = config_raw.split('_', 1)[1]

                try:
                    level = int(level_str)
                except ValueError:
                    logger.warning(f"Invalid level: {level_str}")
                    continue

                ring_number = row.get('Ring', '').strip()
                alias = f"{config_raw}_{ring_number}"
                if not alias or alias == '_':
                    continue

                draw_pct = self._int(row.get('draw'))

                obj, created = m.ProductionRing.objects.update_or_create(
                    alias=alias,
                    defaults={
                        'prod_dev_code': 'p',
                        'is_active': True,
                        'level': level,
                        'status': 'Designed',
                        'x': self._decimal(row.get('AVG_BROW_X')),
                        'y': self._decimal(row.get('AVG_BROW_Y')),
                        'z': self._decimal(row.get('AVG_BROW_Z')),
                        'oredrive': oredrive,
                        'ring_number_txt': ring_number,
                        'dump': self._decimal(row.get('Dump')),
                        'azimuth': self._decimal(row.get('Azimuth')),
                        'burden': row.get('BurdenValue'),
                        'holes': self._int(row.get('Holes')),
                        'diameters': row.get('Diameters'),
                        'drill_meters': self._decimal(row.get('Total Drill')),
                        'drill_look_direction': row.get('LookDirection'),
                        'designed_to_suit': row.get('Rig'),
                        'blastsolids_volume': self._decimal(row.get('BlastSolidsVolume')),
                        'draw_percentage': draw_pct,
                        'in_flow': draw_pct == 100,
                        'design_date': date.today().isoformat()
                    }
                )

                self.ring_map[alias] = obj
                logger.info(
                    f"{'Created' if created else 'Updated'} ring: {alias}")

        except Exception as e:
            logger.error(f"Error processing ring file: {e}", exc_info=True)
            raise

    def attach_hole_data(self, hole_file):
        try:
            reader = csv.DictReader(io.StringIO(
                hole_file.read().decode('utf-8')))
            holes_by_ring = {}

            for row in reader:
                ring_id = row.get('RingID', '').strip()
                if not ring_id:
                    logger.warning(f"Row missing RingID: {row}")
                    continue

                holes_by_ring.setdefault(ring_id, []).append({
                    k: v.strip() if isinstance(v, str) else v
                    for k, v in row.items() if k.strip() in self.HOLE_DATA_HEADERS
                })

            for alias, ring in self.ring_map.items():
                ring_number = ring.ring_number_txt
                ring_holes = holes_by_ring.get(ring_number)

                if ring_holes:
                    ring.hole_data = ring_holes
                    ring.save()
                    logger.info(
                        f"Attached {len(ring_holes)} holes to ring: {alias}")
                else:
                    logger.warning(f"No holes found for ring: {alias}")

        except Exception as e:
            logger.error(f"Error processing hole file: {e}", exc_info=True)
            raise

    def _decimal(self, value):
        try:
            return Decimal(value.strip()) if value else None
        except Exception:
            return None

    def _int(self, value):
        try:
            return int(value.strip()) if value else None
        except Exception:
            return None


class ProdOrphans():
    def __init__(self) -> None:
        self.threshold_dist = None
        self.error_msg = None
        self.warning_msg = None

        self.fetch_threshold_dist()

    def process_orphans(self):
        matches = 0
        orphans = m.ProductionRing.objects.filter(concept_ring__isnull=True)
        for orphan in orphans:
            # Find candidate FlowModelConceptRing with the same level
            candidates = cm.FlowModelConceptRing.objects.filter(
                level=orphan.level)

            # Annotate candidates with the distance between their coordinates (x, y) and the orphan
            candidates = candidates.annotate(
                distance=ExpressionWrapper(
                    Sqrt(
                        (F('x') - Value(orphan.x)) * (F('x') - Value(orphan.x)) +
                        (F('y') - Value(orphan.y)) * (F('y') - Value(orphan.y))
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

        if self.error_msg:
            return {"msg": {"type": "error", "body": self.error_msg}, "status_code": 500}
        return {"processed_count": orphans.count(), "matched": matches}

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
        return m.ProductionRing.objects.filter(
            is_active=True,
            concept_ring__isnull=True,
            location_id=location_id
        ).exists()
