from django.db import transaction
from django.shortcuts import render
from django.http import JsonResponse

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

import logging
import pandas as pd
import prod_concept.models as m
import prod_concept.api.serializers as s

from settings.models import ProjectSetting
from prod_actual.models import ProductionRing
from prod_concept.api.views.mining_direction import MiningDirectionView
from common.functions.block_adjacency import BlockAdjacencyFunctions

from datetime import datetime
from decimal import Decimal


class UploadConceptRingsView(generics.CreateAPIView):
    serializer_class = s.SingleFileSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data['file']
        if file:
            try:
                crfh = ConceptRingsFileHandler()
                handler_response = crfh.handle_flow_concept_file(request, file)

                return Response(handler_response, status=status.HTTP_202_ACCEPTED)
            except Exception as e:
                # Handle general exceptions with a 500 Internal Server Error response
                print(str(e))
                return Response({"status": "error", "detail": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConceptRingsFileHandler():
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rings_created = 0
        self.rings_updated = 0
        self.rings_orphaned = 0
        self.error_msg = None
        self.success_msg = None
        self.user = ''
        self.touched_levels = set()
        self.succession_data = []

    def handle_flow_concept_file(self, request, file):
        self.user = request.user
        self.read_flow_concept_file(file)
        # b = BlockAdjacencyFunctions()
        # b.remap_levels(self.touched_levels)
        # self.update_block_links()

        # =============== prob one time for now
        # md = MiningDirectionView()
        # md.update_mining_direction()

        if self.error_msg:
            return {'msg': self.error_msg, 'msg_type': 'error'}
        else:

            self.success_msg = f'{self.rings_created} Conceptual rings created, {self.rings_updated} updated'
            return {'msg': self.success_msg, 'msg_type': 'success'}

    def read_flow_concept_file(self, file):
        # Fetch the required columns from the settings
        try:
            project_setting = ProjectSetting.objects.get(
                key='concept_csv_headers')
            required_columns = project_setting.value
            required_columns_list = list(required_columns.values())
        except ProjectSetting.DoesNotExist:
            self.error_msg = "CSV file headers blank, see FM Concept tab in settings"
            self.logger.error(self.error_msg)
            return

        try:
            file.seek(0)
            df = pd.read_csv(file, usecols=required_columns_list,
                             encoding='utf-8', encoding_errors='replace')
        except ValueError as e:
            df_check = pd.read_csv(file)
            missing_columns = [
                col for col in required_columns_list if col not in df_check.columns]
            self.error_msg = f"Missing columns in the file: {', '.join(missing_columns)}" if missing_columns else str(
                e)
            self.logger.error(f"Error: {self.error_msg}")
            return

        df2 = df.fillna("")

        for _, row in df2.iterrows():
            try:
                drv_num = int(row[required_columns["drive"]])
                bs_id = row[required_columns["id"]]
                level = self.number_fix(row[required_columns["level"]])
                self.touched_levels.add(level)

                # Store successors/predecessors
                self.succession_data.append({
                    'id': bs_id,
                    'successors': row[required_columns["successors"]],
                    'predecessors': row[required_columns["predecessors"]],
                })

                obj, created = m.FlowModelConceptRing.objects.update_or_create(
                    blastsolids_id=bs_id,
                    defaults={
                        'description': row[required_columns["name"]],
                        'is_active': True,
                        'level': level,
                        'heading': row[required_columns["heading"]],
                        'drive': self.number_fix(row[required_columns["drive"]]),
                        'loc': row[required_columns["loc"]],
                        'x': self.number_fix(row[required_columns["x"]]),
                        'y': self.number_fix(row[required_columns["y"]]),
                        'z': self.number_fix(row[required_columns["z"]]),
                        'pgca_modelled_tonnes': self.number_fix(row[required_columns["tonnes"]]),
                        'draw_zone': self.number_fix(row[required_columns["draw_zone"]]),
                        'density': self.number_fix(row[required_columns["density"]]),
                        'modelled_au': self.number_fix(row[required_columns["au"]]),
                        'modelled_cu': self.number_fix(row[required_columns["cu"]]),
                    }
                )

                if created:
                    self.rings_created += 1
                else:
                    self.rings_updated += 1

            except ValueError as ve:
                self.logger.warning(f"Skipping row due to ValueError: {ve}")
            except Exception as e:
                self.logger.error(f"Error: {e}")
                self.error_msg = str(e)
                self.logger.error(f"Row causing the error: {row}")
                self.logger.exception("Traceback:")
                return

    def has_location_changed(self, existing_record, new_x, new_y, new_z):
        new_x = Decimal(new_x)
        new_y = Decimal(new_y)
        new_z = Decimal(new_z)

        if abs(existing_record.x - new_x) > Decimal('0.1'):
            return True
        if abs(existing_record.y - new_y) > Decimal('0.1'):
            return True
        if abs(existing_record.z - new_z) > Decimal('0.1'):
            return True
        return False

    def create_orphaned_rings(self, location):
        rings_to_orphan = ProductionRing.objects.filter(
            location_id=location.location_id)

        self.rings_orphaned = rings_to_orphan.count()
        rings_to_orphan.update(concept_ring=None)

        return

    def number_fix(self, cell):
        if isinstance(cell, str):
            try:
                return float(cell)
            except ValueError:
                return 0
        else:
            return cell

    def update_block_links(self):
        # Step 1: Delete all existing links
        for b in self.succession_data:
            block_id = b['id']

            # Get the block using its blastsolids_id
            block = m.FlowModelConceptRing.objects.filter(
                blastsolids_id=block_id).first()
            if not block:
                # Skip if the block doesn't exist
                continue

            # Delete all existing links for this block (both as block and linked)
            m.BlockLink.objects.filter(block=block).delete()

        # Step 2: Create new links
        for b in self.succession_data:
            block_id = b['id']

            # Get the block using its blastsolids_id
            block = m.FlowModelConceptRing.objects.filter(
                blastsolids_id=block_id).first()
            if not block:
                # Skip if the block doesn't exist
                continue

            # Create new links for successors
            if b['successors']:
                successor_ids = b['successors'].split(';')
                for succ_id in successor_ids:
                    successor = m.FlowModelConceptRing.objects.filter(
                        blastsolids_id=succ_id).first()
                    if successor:
                        m.BlockLink.objects.create(
                            block=block,
                            linked=successor,
                            direction='S'
                        )
                    else:
                        print(
                            f'{b["id"]}: Successor {succ_id} not in concept database.')

            # Create new links for predecessors
            if b['predecessors']:
                predecessor_ids = b['predecessors'].split(';')
                for pred_id in predecessor_ids:
                    predecessor = m.FlowModelConceptRing.objects.filter(
                        blastsolids_id=pred_id).first()
                    if predecessor:
                        m.BlockLink.objects.create(
                            block=block,
                            linked=predecessor,
                            direction='P'
                        )
                    else:
                        print(
                            f'{b["id"]}: Predecessor {succ_id} not in concept database.')
