from rest_framework import generics, status
from rest_framework.response import Response

import whatif.api.serializers as s
import whatif.models as m
import prod_concept.models as pcm
import prod_actual.models as pam

from common.functions.status import Status
from common.functions.block_adjacency import BlockAdjacencyFunctions
from settings.models import ProjectSetting

from time import strftime
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import transaction
from django.db.models import F, Q, ExpressionWrapper
from django.db.models.functions import Abs, ExtractMonth, ExtractYear
from datetime import datetime, timedelta
from decimal import Decimal
from pprint import pprint
from copy import deepcopy


import csv
import time
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
            handler_response = sfh.handle_schedule_file(
                request, file, scenario_name)

            return Response(handler_response, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle general exceptions with a 500 Internal Server Error response
            print(str(e))
            return Response({'msg': {"type": "error", "body": "Internal Server Error"}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScenarioListView():
    pass


class ScheduleFileHandler():
    def __init__(self):
        self.opposite_direction = {'N': 'S', 'NE': 'SW', 'E': 'W',
                                   'SE': 'NW', 'S': 'N', 'SW': 'NE', 'W': 'E', 'NW': 'SE'}
        self.mining_direction = None
        self.min_precharge_amount = 7.5  # meters
        self.min_amount_drilled = 10  # meters
        self.error_msg = ""
        self.assumed_mtrs_in_concept_ring = 165
        
        self.scenario = None
        #self.scenario = m.Scenario.objects.get(scenario=43)

    def handle_schedule_file(self, request, file, scenario_name):
        user = request.user

        scenario = m.Scenario.objects.create(
            name=scenario_name,
            owner=user,
            datetime_stamp=timezone.now()
        )
        self.scenario = scenario

        # Process the uploaded CSV file
        print("reading csv into scenario table")
        rows_processed = self.read_csv(file)
        if self.error_msg:
            return {'msg': {'body': msg, 'type': 'error'}}

        print("marrying concept rings")
        self.marry_concept_rings()

        self.run_scenario()
        

        # rows_processed = 'All'
        msg = f'{rows_processed} rows processed successfully'

        return {'msg': {'body': msg, 'type': 'success'}}



    def read_csv(self, file):
        """
        Read the CSV file and create SchedSim entries for each row.
        """
        # Fetch the required columns from the settings
        try:
            project_setting = ProjectSetting.objects.get(
                key='drill_scenario_file_headers')
            required_columns = project_setting.value
        except ProjectSetting.DoesNotExist:
            self.error_msg = "CSV file headers blank, see FM Concept tab in settings"
            return

        rows_processed = 0

        # Open the file and read it as a CSV
        decoded_file = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        # Define the input format with both date and time, to parse correctly
        date_format_input = "%d/%m/%Y %H:%M"  # Format with time, matching CSV
        date_format_output = "%Y-%m-%d"  # Desired output format for date only
        blastsolid = None

        for row in reader:
            # Skip duplicate rows
            blastsolid_id = row.get(required_columns.get("id", ''), '')
            if blastsolid == blastsolid_id:
                continue
            else:
                blastsolid = blastsolid_id

            # Parse start_date and finish_date, extracting only the date part
            start_date_raw = row.get(required_columns.get("start", ''), '')
            finish_date_raw = row.get(required_columns.get("finish", ''), '')

            try:
                start_date = datetime.strptime(
                    start_date_raw, date_format_input).date() if start_date_raw else None
            except ValueError:
                self.error_msg = f'Unreadable start date at line {rows_processed}'
                return

            try:
                finish_date = datetime.strptime(
                    finish_date_raw, date_format_input).date() if finish_date_raw else None
            except ValueError:
                finish_date = None

            # Create a SchedSim object for each row
            m.SchedSim.objects.create(
                bogging_block=None,  # Assuming you'll handle bogging_block logic separately
                production_ring=None,  # Assuming you'll handle production_ring logic separately
                scenario=self.scenario,
                description=row.get(required_columns.get("name", ''), ''),
                blastsolids_id=blastsolid_id,
                start_date=start_date,
                finish_date=finish_date,
                level=int(row.get(required_columns.get("level", ''), 0)),
                json={},  # Handle json field if required
            )

            rows_processed += 1

        return rows_processed

    def run_scenario(self):
        all_sched = m.SchedSim.objects.filter(scenario=self.scenario)
        
        for sched_item in all_sched:
            drv_name = m.FlowModelConceptRing.objects.get(blastsolids_id=sched_item.blastsolids_id).description
            self.mining_direction = pcm.MiningDirection.objects.get(description=drv_name).mining_direction

            sched_item.description = drv_name
            sched_item.last_charge_block = self.calc_last_charged_block(sched_item)
            sched_item.save()
            self.populate_last_drill_block(sched_item)


            


    def marry_concept_rings(self):
        sched_to_marry = m.SchedSim.objects.filter(
            scenario=self.scenario)
        updated_sched_blocks = []

        for sched_block in sched_to_marry:
            try:
                concept_block = m.FlowModelConceptRing.objects.get(
                    blastsolids_id=sched_block.blastsolids_id)
            except m.FlowModelConceptRing.DoesNotExist:
                concept_block = None
            except m.FlowModelConceptRing.MultipleObjectsReturned:
                concept_block = None

            # Update the concept_ring field
            sched_block.bogging_block = concept_block
            updated_sched_blocks.append(sched_block)

        # Use bulk_update to save all changes at once
        m.SchedSim.objects.bulk_update(
            updated_sched_blocks, ['bogging_block'])


    def is_block_in_flow_concept(self, sched_sim):
        blastsolid = sched_sim.blastsolids_id
        count = pcm.FlowModelConceptRing.objects.filter(
            is_active=True, blastsolids_id=blastsolid).count()
        if count > 0:
            return True
        else:
            return False


    def calc_last_charged_block(self, sched_item):
        baf = BlockAdjacencyFunctions()
        last_charged_block = None
        charged = None

        if sched_item.bogging_block:
            charged = baf.step_dist(sched_item.bogging_block, self.mining_direction, self.min_precharge_amount)
        if sched_item.description:
            # might already be charged past calc pos
            last_charged_block = self.get_current_last_block_of_status(sched_item.description, self.mining_direction, 'Charged')
        if charged:
            if last_charged_block:
                if last_charged_block != charged:
                    if baf.is_in_general_mining_direction(sched_item.bogging_block, last_charged_block, self.mining_direction):
                        return last_charged_block
            return charged
        return None



    def get_current_last_block_of_status(self, description, mining_direction, status):
        baf = BlockAdjacencyFunctions()
        designed_rings = pam.ProductionRing.objects.filter(is_active=True, status=status, concept_ring__description=description)
        if designed_rings:
            last_ring = baf.get_last_block_in_set(designed_rings, mining_direction)
            return last_ring.concept_ring
        else:
            return None
        
    def get_last_designed_block(self, description, mining_direction):
        baf = BlockAdjacencyFunctions()
        designed_rings = pam.ProductionRing.objects.filter(is_active=True, concept_ring__description=description)
        if designed_rings:
            last_ring = baf.get_last_block_in_set(designed_rings, mining_direction)
            return last_ring.concept_ring
        else:
            return None


    def populate_last_drill_block(self, sched_item):
        baf = BlockAdjacencyFunctions()
        if sched_item.last_charge_block and self.mining_direction:
            self.add_min_drilling(sched_item)
            if sched_item.description:
                eod = baf.get_last_block_in_drive(sched_item.description, self.mining_direction)
                if sched_item.last_drill_block and sched_item.last_drill_block != eod:
                    last_drilled = self.get_current_last_block_of_status(sched_item.description, self.mining_direction, 'Drilled')
                    if last_drilled:
                        if baf.is_in_general_mining_direction(sched_item.last_drill_block, last_drilled, self.mining_direction):
                            sched_item.last_drill_block = last_drilled
                            sched_item.save()
                    self.interference_from_others(sched_item, eod)
                self.interfere_with_others(sched_item)


    def add_min_drilling(self, sched_item):
        baf = BlockAdjacencyFunctions()
        if sched_item.last_charge_block and self.mining_direction:
            min_drill = baf.step_dist(sched_item.last_charge_block, self.mining_direction, self.min_amount_drilled)
            if min_drill:
                if sched_item.last_drill_block:
                    if baf.is_in_general_mining_direction(sched_item.last_drill_block, min_drill, self.mining_direction):
                        sched_item.last_drill_block = min_drill
                        sched_item.save()
                else:
                    sched_item.last_drill_block = min_drill
                    sched_item.save()

        

    def interference_from_others(self, sched_item, eod):
        baf = BlockAdjacencyFunctions()
        adj_drives = baf.get_adjacent_drives(sched_item.last_drill_block)
        for adj_drive in adj_drives:
            # if no adj charged then no interference
            adj_schedsim = self.get_adj_schedsim(adj_drive, sched_item)
            if adj_schedsim:
                adj_charged = adj_schedsim.last_charge_block
                if adj_charged:
                    # might be far enough away
                    dist = baf.get_dist_to_block(sched_item.last_drill_block, adj_charged)
                    drill = sched_item.last_drill_block
                    while dist < self.min_amount_drilled and drill != eod:
                        # get interfered with
                        next_block = baf.step_next_block(drill, self.mining_direction)
                        if next_block:
                            drill = next_block
                    sched_item.last_drill_block = drill
                    sched_item.save()



    
    def interfere_with_others(self, sched_item):
        # now for the fun stuff
        baf = BlockAdjacencyFunctions()
        adj_drives = baf.get_adjacent_drives(sched_item.last_charge_block)
        for adj_drive in adj_drives:
            adj_mining_dir = pcm.MiningDirection.objects.get(description=sched_item.description).mining_direction
            adj_block = baf.get_block_from_adj_named_od(sched_item.last_charge_block, adj_drive)
            adj_schedsim = self.get_adj_schedsim(adj_drive, sched_item)
            if not adj_schedsim:
                # might have nothing, needs drilling
                adj_schedsim = m.SchedSim.objects.create(
                    scenario=self.scenario,
                    description=adj_drive,
                    start_date=sched_item.start_date,
                    level=sched_item.level,
                    json={},
                )
                adj_schedsim.save()

                adj_schedsim.last_charge_block = self.calc_last_charged_block(adj_schedsim)
                adj_schedsim.save()
            drill = baf.step_dist(adj_block, adj_mining_dir, self.min_amount_drilled)
            # compare with what is existing
            if adj_schedsim.start_date == sched_item.start_date:
                if adj_schedsim.last_drill_block and drill:
                    if baf.is_in_general_mining_direction(adj_schedsim.last_drill_block, drill, adj_mining_dir):
                        adj_schedsim.last_drill_block = drill
                        adj_schedsim.save()
                else:
                    adj_schedsim.last_drill_block = drill
                    adj_schedsim.save()
            else:
                if adj_schedsim.last_drill_block and drill:
                    in_mining_dir = baf.is_in_general_mining_direction(drill, adj_schedsim.last_drill_block, adj_mining_dir)
                    if adj_schedsim.last_drill_block and in_mining_dir:
                        drill = adj_schedsim.last_drill_block

                m.SchedSim.objects.create(
                    bogging_block=adj_schedsim.bogging_block,
                    production_ring=adj_schedsim.production_ring,
                    last_charge_block=adj_schedsim.last_charge_block,
                    last_drill_block=drill,
                    scenario=self.scenario,
                    description=adj_schedsim.description,
                    start_date=sched_item.start_date,
                    finish_date=sched_item.finish_date,
                    level=sched_item.level,
                    json={},
                )   



    def get_adj_schedsim(self, description, sched_item):
        '''
        Input: Block description and start date
        
        Output: The last scheduled item in the drive on or before date
        '''

        last_sched_item = (m.SchedSim.objects
        .filter(description=description, start_date__lte=sched_item.start_date)
        .order_by('-start_date')
        .first())


        return last_sched_item
    


    #============== COUNTING METHODS =====================


    def calculate_drill_sums(self):
        drives = m.SchedSim.objects.values_list('description', flat=True).distinct()

        for drive in drives:
            drive_schedule = m.SchedSim.objects.filter(description=drive).order_by('start_date')

            last_designed = self.get_last_designed_block(drive, self.mining_direction)
            prev_schedule_block = None
            is_start_of_drive = False # adds rings and meters from first block

            for sched in drive_schedule:
                if sched.last_drill_block:
                    if not prev_schedule_block and self.mining_direction:
                        prev_schedule_block = self.get_current_last_block_of_status(drive, self.mining_direction, 'Drilled')
                        if not prev_schedule_block:
                            is_start_of_drive = True 
                            baf = BlockAdjacencyFunctions()
                            prev_schedule_block = baf.find_first_block(drive, self.mining_direction)
                    else:
                        print("Missing mining direction when calculating drill sums")

                    self.get_rings_between(prev_schedule_block, sched, is_start_of_drive)
                    prev_schedule_block = sched.last_drill_block


                        
    def get_rings_between(self, start_block, sched_item, is_start_of_drive, prev_block_had_rings):
        baf = BlockAdjacencyFunctions()
        
        blocks_to_count = []
        if is_start_of_drive:
            blocks_to_count.append(start_block)
        current_block = start_block
        while current_block != sched_item.last_drill_block:
            block = baf.step_next_block(current_block, self.mining_direction)
            blocks_to_count.append(block)
            current_block = block

        ring_count = 0
        meter_count = 0
        
        for block in blocks_to_count:
            rings_in_block = pam.ProductionRing.objects.filter(is_active=True, concept_ring=block)
            rings = rings_in_block.count()
            if rings == 0:
                if prev_block_had_rings:
                    prev_block_had_rings = False
                else:
                    meter_count += self.assumed_mtrs_in_concept_ring
                    ring_count += 1
            else:
                prev_block_had_rings = True
                for ring in rings_in_block:
                    meter_count += ring.drill_meters
                    ring_count += 1

        


