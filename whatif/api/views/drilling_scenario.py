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
        self.min_precharge_amount = 7.5  # meters
        self.min_amount_drilled = 10  # meters
        self.missing_drive_found_blocks = []
        self.error_msg = ""

        
        self.scenario = None
        self.scenario = m.Scenario.objects.get(scenario=43)

    def handle_schedule_file(self, request, file, scenario_name):
        user = request.user

        # scenario = m.Scenario.objects.create(
        #     name=scenario_name,
        #     owner=user,
        #     datetime_stamp=timezone.now()
        # )
        # self.scenario = scenario

        # Process the uploaded CSV file
        # print("reading csv into scenario table")
        # rows_processed = self.read_csv(file)
        # if self.error_msg:
        #     return {'msg': {'body': msg, 'type': 'error'}}

        # print("marrying concept rings")
        # self.marry_concept_rings()
        # print("populating mining direction")
        # self.populate_mining_direction()
        # print("finished processing directions")
        self.run_scenario()

        rows_processed = 'All'
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
        
        # for sched_item in all_sched:
        #     sched_item.last_charge_block = self.calc_last_charged_block(sched_item)
        #     sched_item.save()
        #     self.populate_last_drill_block(sched_item)


            


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

    def populate_mining_direction(self):
        to_update = m.SchedSim.objects.filter(scenario=self.scenario)
        updated_blocks = []

        for sched_block in to_update:
            direction = self.calc_mining_direction(sched_block)
            sched_block.mining_direction = direction
            updated_blocks.append(sched_block)

        # Perform a bulk update on mining_direction
        m.SchedSim.objects.bulk_update(
            updated_blocks, ['mining_direction'])

    def calc_mining_direction(self, sched_sim):
        # Sched_sim, yeah i know, its a shit name for a simulated scheduled block.. but what to do?

        if sched_sim.blastsolids_id and self.is_block_in_flow_concept(sched_sim):
            use_dates = self.direction_check_sched_dates(sched_sim)
            if use_dates:
                return use_dates
            use_status = self.direction_check_status(sched_sim)
            if use_status:
                return use_status
            return self.direction_start_of_drive(sched_sim)
        elif sched_sim.description:
            use_status = self.direction_check_status(sched_sim)
            if use_status:
                return use_status
            use_prox_to_start = self.direction_start_of_drive(sched_sim)
            if use_prox_to_start:
                return use_prox_to_start
        else:
            print("No way of determining mining direction")
            return None

    def is_block_in_flow_concept(self, sched_sim):
        blastsolid = sched_sim.blastsolids_id
        count = pcm.FlowModelConceptRing.objects.filter(
            is_active=True, blastsolids_id=blastsolid).count()
        if count > 0:
            return True
        else:
            return False



    def direction_check_sched_dates(self, sched_sim):
        sched_same_drive = m.SchedSim.objects.filter(
            scenario=self.scenario,
            description=sched_sim.description
        )
        if sched_same_drive.count() > 1:
            current_block = sched_sim.bogging_block
            ba = BlockAdjacencyFunctions()

            for block_same_drv in sched_same_drive:
                if ba.is_adjacent(current_block, block_same_drv.bogging_block):
                    current_block_date = sched_sim.start_date
                    block_same_drv_date = block_same_drv.start_date

                    if current_block_date < block_same_drv_date:
                        direction = ba.determine_direction(
                            current_block, block_same_drv.bogging_block)
                    elif current_block_date == block_same_drv_date:
                        continue
                    else:
                        direction = ba.determine_direction(
                            block_same_drv.bogging_block, current_block)
                    return direction
        else:
            return None

    def direction_check_status(self, sched_sim):
        oredrive_desc = sched_sim.description
        designed_rings = pam.ProductionRing.objects.filter(
            is_active=True, concept_ring__description=oredrive_desc)

        if designed_rings:
        # Collect possible states in a single dictionary
            possible_states = {
                'bogging': designed_rings.filter(status='Bogging'),
                'charged': designed_rings.filter(status='Charged'),
                'drilled': designed_rings.filter(status='Drilled'),
                'designed': designed_rings.filter(status='Designed')
            }

            reference_state = None

            for state_name, queryset in possible_states.items():
                if queryset.exists():
                    if reference_state is None:
                        reference_state = queryset.first()
                    else:
                        comparator_ring = queryset.first()
                        baf = BlockAdjacencyFunctions()
                        dir = baf.determine_direction(reference_state, comparator_ring)
                        return dir
        return None

    def direction_start_of_drive(self, sched_sim):
        # Nothing designed, we are close to start of drive
        oredrive_desc = sched_sim.description
        blocks_in_drive = pcm.FlowModelConceptRing.objects.filter(description=oredrive_desc)
        this_block_queryset = pcm.FlowModelConceptRing.objects.filter(blastsolids_id=sched_sim.blastsolids_id)
        if this_block_queryset:
            this_block = this_block_queryset.first()
            farthest_block = self.get_farthest_block(this_block, blocks_in_drive)
            baf = BlockAdjacencyFunctions()
            return baf.determine_direction(this_block, farthest_block)
        else:
            print(f'{oredrive_desc} block {sched_sim.blastsolids_id} does not exist in concept')
            return None
        


    def calc_last_charged_block(self, sched_item):
        baf = BlockAdjacencyFunctions()
        last_charged_block = None
        charged = None

        if sched_item.mining_direction:
            if sched_item.bogging_block:
                charged = baf.step_dist(sched_item.bogging_block, sched_item.mining_direction, self.min_precharge_amount)
            if sched_item.description:
                # might already be charged past calc pos
                last_charged_block = self.get_current_last_block_of_status(sched_item.description, sched_item.mining_direction, 'Charged')
            if charged:
                if last_charged_block:
                    if last_charged_block != charged:
                        if baf.is_in_general_mining_direction(sched_item.bogging_block, last_charged_block, sched_item.mining_direction):
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


    def populate_last_drill_block(self, sched_item):
        baf = BlockAdjacencyFunctions()
        if sched_item.last_charge_block and sched_item.mining_direction:
            self.add_min_drilling(sched_item)
            if sched_item.description:
                eod = baf.get_last_block_in_drive(sched_item.description, sched_item.mining_direction)
                if sched_item.last_drill_block and sched_item.last_drill_block != eod:
                    last_drilled = self.get_current_last_block_of_status(sched_item.description, sched_item.mining_direction, 'Drilled')
                    if last_drilled:
                        if baf.is_in_general_mining_direction(sched_item.last_drill_block, last_drilled, sched_item.mining_direction):
                            sched_item.last_drill_block = last_drilled
                            sched_item.save()
                    self.interference_from_others(sched_item, eod)
                self.interfere_with_others(sched_item)


    def add_min_drilling(self, sched_item):
        baf = BlockAdjacencyFunctions()
        if sched_item.last_charge_block and sched_item.mining_direction:
            min_drill = baf.step_dist(sched_item.last_charge_block, sched_item.mining_direction, self.min_amount_drilled)
            if min_drill:
                if sched_item.last_drill_block:
                    if baf.is_in_general_mining_direction(sched_item.last_drill_block, min_drill, sched_item.mining_direction):
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
                        next_block = baf.step_next_block(drill, sched_item.mining_direction)
                        if next_block:
                            drill = next_block
                    sched_item.last_drill_block = drill
                    sched_item.save()



    
    def interfere_with_others(self, sched_item):
        # now for the fun stuff
        baf = BlockAdjacencyFunctions()
        adj_drives = baf.get_adjacent_drives(sched_item.last_charge_block)
        for adj_drive in adj_drives:
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
                adj_schedsim.mining_direction = self.calc_mining_dir_without_bog_pos(adj_block, adj_schedsim)
                adj_schedsim.save()
                if adj_schedsim.mining_direction:
                    adj_schedsim.last_charge_block = self.calc_last_charged_block(adj_schedsim)
                    adj_schedsim.save()
            if not adj_schedsim.mining_direction:
                adj_schedsim.mining_direction = self.calc_mining_dir_without_bog_pos(adj_block, adj_schedsim)
                adj_schedsim.save()
            drill = baf.step_dist(adj_block, adj_schedsim.mining_direction, self.min_amount_drilled)
            # compare with what is existing
            if adj_schedsim.start_date == sched_item.start_date:
                if adj_schedsim.last_drill_block and drill:
                    if baf.is_in_general_mining_direction(adj_schedsim.last_drill_block, drill, adj_schedsim.mining_direction):
                        adj_schedsim.last_drill_block = drill
                        adj_schedsim.save()
                else:
                    adj_schedsim.last_drill_block = drill
                    adj_schedsim.save()
            else:
                if adj_schedsim.last_drill_block and drill:
                    in_mining_dir = baf.is_in_general_mining_direction(drill, adj_schedsim.last_drill_block, adj_schedsim.mining_direction)
                    if adj_schedsim.last_drill_block and in_mining_dir:
                        drill = adj_schedsim.last_drill_block

                m.SchedSim.objects.create(
                    bogging_block=adj_schedsim.bogging_block,
                    production_ring=adj_schedsim.production_ring,
                    last_charge_block=adj_schedsim.last_charge_block,
                    last_drill_block=drill,
                    scenario=self.scenario,
                    description=adj_schedsim.description,
                    mining_direction=adj_schedsim.mining_direction,
                    start_date=sched_item.start_date,
                    finish_date=sched_item.finish_date,
                    level=sched_item.level,
                    json={},
                )   


    def calc_mining_dir_without_bog_pos(self, ref_block, schedsim):
        # the suckiest way to find direction
        # assume ref block near start of drive

        baf = BlockAdjacencyFunctions()

        designed = pam.ProductionRing.objects.filter(is_active=True, concept_ring__description=schedsim.description, status='Bogging')
        if designed:
            bogging_block = designed.first().concept_ring
            blastsolid_id = bogging_block.blastsolids_id

            schedsim.bogging_block = bogging_block
            schedsim.blastsolids_id = blastsolid_id
            schedsim.save()

            dir = self.direction_check_status(schedsim)
            if dir:
                return dir
            dir = self.direction_start_of_drive(schedsim)
            return dir
        else:
            drive_blocks = m.FlowModelConceptRing.objects.filter(description=schedsim.description)
            farthest_block = self.get_farthest_block(ref_block, drive_blocks)
            direction = baf.determine_direction(ref_block, farthest_block)
            return direction



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
    
    def get_farthest_block(self, this_block, those_blocks):
        baf = BlockAdjacencyFunctions()
        farthest_block = None
        max_distance = 0
        for block in those_blocks:
            distance = baf.get_dist_to_block(this_block, block)
            if distance > max_distance:
                max_distance = distance
                farthest_block = block
        return farthest_block

    #============== COUNTING METHODS =====================


    def calculate_drill_ring_sums(self):
        drives = m.SchedSim.objects.values_list('description', flat=True).distinct()

        for drive in drives:
            drive_schedule = m.SchedSim.objects.filter(description=drive).order_by('start_date')

            cumulative_drill_rings = 0
            previous_schedule_date = None

            for sched in drive_schedule:
                if previous_schedule_date:
                    # Calculate drill rings between the previous and current schedule date
                    drill_rings_between = m.SchedSim.objects.filter(
                        description=drive,
                        start_date__gt=previous_schedule_date,
                        start_date__lte=sched.start_date
                    ).count()  # or Sum('drill_rings') if rings are stored elsewhere

                    # Update cumulative drill rings
                    cumulative_drill_rings += drill_rings_between

                # Update current record with the cumulative drill rings sum
                sched.sum_drill_rings_from_prev = cumulative_drill_rings
                sched.save()

                # Set the current schedule date as previous for the next iteration
                previous_schedule_date = sched.start_date
