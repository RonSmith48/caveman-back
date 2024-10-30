from rest_framework import generics, status
from rest_framework.response import Response

import whatif.api.serializers as s
import whatif.models as m
import prod_concept.models as pcm

from time import strftime
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q, ExpressionWrapper
from django.db.models.functions import Abs
from datetime import datetime, timedelta
from decimal import Decimal
from common.functions.shkey import Shkey

import csv
import logging
import pandas as pd


class UploadScheduleView(generics.CreateAPIView):
    serializer_class = s.SingleFileSerializer

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data['file']
        scenario_name = request.data.get('scenario_name')

        try:
            sfh = ScheduleFileHandler()
            handler_response = sfh.handle_schedule_file(request, file, scenario_name)

            return Response(handler_response, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle general exceptions with a 500 Internal Server Error response
            print(str(e))
            return Response({'msg': {"type": "error", "body": "Internal Server Error"}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ScenarioListView():
    pass
        
class ScheduleFileHandler():
    def __init__(self) -> None:
        pass

    def handle_schedule_file(self, request, file, scenario_name):
        user = request.user

        # Create a new Scenario instance
        scenario = m.Scenario.objects.create(
            name=scenario_name,
            owner=user,
            datetime_stamp=timezone.now()
        )

        # Process the uploaded CSV file
        rows_processed = self.read_csv(file, scenario)
        msg = f'{rows_processed} rows processed successfully'

        return {'msg':{'body': msg, 'type':'success'}}

    def read_csv(self, file, scenario):
        """
        Read the CSV file and create ScheduleSimulator entries for each row.
        """
        rows_processed = 0

        # Open the file and read it as a CSV
        decoded_file = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            # Create a ScheduleSimulator object for each row
            m.ScheduleSimulator.objects.create(
                concept_ring=None,  # Assuming you'll handle concept_ring logic separately
                production_ring=None,  # Assuming you'll handle production_ring logic separately
                scenario=scenario,
                blastsolids_id=row.get('ID', ''),
                start_date=row.get('Start', ''),
                finish_date=row.get('Finish', ''),
                level=int(row.get('LEVEL', 0)),
                x=row.get('X', 0),
                y=row.get('Y', 0),
                z=row.get('Z', 0),
                json={},  # Handle json field if required
            )

            rows_processed += 1

        return rows_processed
    
    def run_scenario(self):
        pass

    def marry_designed_rings(self):
        pass

    def marry_concept_rings(self):
        pass

    