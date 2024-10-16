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

    def handle_flow_concept_file(self, request, file):
        self.user = request.user
        self.read_flow_concept_file(file)
        if self.error_msg:
            return {'msg': self.error_msg, 'msg_type': 'error'}
        else:
            self.success_msg = f'{self.rings_created} Conceptual rings created, {
                self.rings_updated} updated, {self.rings_orphaned} rings orphaned'
            return {'msg': self.success_msg, 'msg_type': 'success'}

    def read_flow_concept_file(self, file):
        # Fetch the required columns from the settings
        try:
            project_setting = ProjectSetting.objects.get(key='fm_file_headers')
            required_columns = project_setting.value
            required_columns_list = list(required_columns.values())
        except ProjectSetting.DoesNotExist:
            self.error_msg = "CSV file headers blank, see FM Concept tab in settings"
            self.logger.error(self.error_msg)
            return

        try:
            df = pd.read_csv(file, usecols=required_columns_list)
        except ValueError as e:
            df_check = pd.read_csv(file)
            missing_columns = [
                col for col in required_columns_list if col not in df_check.columns]

            if missing_columns:
                self.error_msg = f"Missing columns in the file: {
                    ', '.join(missing_columns)}"
            else:
                self.error_msg = str(e)

            self.logger.error(f"Error: {self.error_msg}")
            return

        # Replace all the 'nan' values for 'None'
        df2 = df.fillna("")

        try:
            with transaction.atomic():
                for _, row in df2.iterrows():
                    try:
                        drv_num = int(row[required_columns["drive"]])
                        create_record = True
                        bs_id = row[required_columns["id"]]

                        # Create a savepoint
                        sid = transaction.savepoint()

                        try:
                            existing_record = m.FlowModelConceptRing.objects.get(
                                blastsolids_id=bs_id)
                            new_x = self.number_fix(row[required_columns["x"]])
                            new_y = self.number_fix(row[required_columns["y"]])
                            new_z = self.number_fix(row[required_columns["z"]])
                            if self.has_location_changed(existing_record, new_x, new_y, new_z):
                                self.create_orphaned_rings(
                                    existing_record.location_id)

                            # Update the existing record
                            existing_record.description = row[required_columns["name"]]
                            existing_record.inactive = False
                            existing_record.level = self.number_fix(
                                row[required_columns["level"]])
                            existing_record.heading = row[required_columns["heading"]]
                            existing_record.drive = self.number_fix(
                                row[required_columns["drive"]])
                            existing_record.loc = row[required_columns["loc"]]
                            existing_record.x = new_x
                            existing_record.y = new_y
                            existing_record.z = new_z
                            existing_record.pgca_modelled_tonnes = self.number_fix(
                                row[required_columns["tonnes"]])
                            existing_record.draw_zone = self.number_fix(
                                row[required_columns["draw_zone"]])
                            existing_record.density = self.number_fix(
                                row[required_columns["density"]])
                            existing_record.modelled_au = self.number_fix(
                                row[required_columns["au"]])
                            existing_record.modelled_cu = self.number_fix(
                                row[required_columns["cu"]])

                            if self.error_msg:
                                transaction.savepoint_rollback(sid)
                                return
                            existing_record.save()
                            create_record = False
                        except m.FlowModelConceptRing.DoesNotExist:
                            # Create a new record
                            m.FlowModelConceptRing.objects.create(
                                description=row[required_columns["name"]],
                                is_active=True,
                                level=self.number_fix(
                                    row[required_columns["level"]]),
                                blastsolids_id=row[required_columns["id"]],
                                heading=row[required_columns["heading"]],
                                drive=self.number_fix(
                                    row[required_columns["drive"]]),
                                loc=row[required_columns["loc"]],
                                x=self.number_fix(row[required_columns["x"]]),
                                y=self.number_fix(row[required_columns["y"]]),
                                z=self.number_fix(row[required_columns["z"]]),
                                pgca_modelled_tonnes=self.number_fix(
                                    row[required_columns["tonnes"]]),
                                draw_zone=self.number_fix(
                                    row[required_columns["draw_zone"]]),
                                density=self.number_fix(
                                    row[required_columns["density"]]),
                                modelled_au=self.number_fix(
                                    row[required_columns["au"]]),
                                modelled_cu=self.number_fix(
                                    row[required_columns["cu"]])
                            )
                        if self.error_msg:
                            transaction.savepoint_rollback(sid)
                            return

                        # Release the savepoint
                        transaction.savepoint_commit(sid)

                        if create_record:
                            self.rings_created += 1
                        else:
                            self.rings_updated += 1
                    except ValueError:
                        pass
        except Exception as e:
            self.logger.error(f"Error: {e}")
            self.error_msg = str(e)
            self.logger.error(f"Row causing the error: {row}")
            self.logger.exception("Traceback:")
            transaction.savepoint_rollback(sid)
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