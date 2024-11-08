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
        # self.scenario = None
        self.scenario = m.Scenario.objects.get(scenario=4)

    def handle_schedule_file(self, request, file, scenario_name):
        user = request.user

        # Create a new Scenario instance
        # scenario = m.Scenario.objects.create(
        #     name=scenario_name,
        #     owner=user,
        #     datetime_stamp=timezone.now()
        # )
        # self.scenario = scenario

        # # Process the uploaded CSV file
        # print("reading csv into scenario table")
        # rows_processed = self.read_csv(file)
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

        for row in reader:
            # Parse start_date and finish_date, extracting only the date part
            start_date_raw = row.get(required_columns.get("start", ''), '')
            finish_date_raw = row.get(required_columns.get("finish", ''), '')

            try:
                start_date = datetime.strptime(
                    start_date_raw, date_format_input).date() if start_date_raw else None
            except ValueError:
                start_date = None

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
                blastsolids_id=row.get(required_columns.get("id", ''), ''),
                start_date=start_date,
                finish_date=finish_date,
                level=int(row.get(required_columns.get("level", ''), 0)),
                json={},  # Handle json field if required
            )

            rows_processed += 1

        return rows_processed

    def run_scenario(self):
        self.find_missing_drives()




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

        if self.is_block_in_flow_concept(sched_sim):
            use_dates = self.direction_check_sched_dates(sched_sim)
            if use_dates:
                return use_dates
            use_status = self.direction_check_status(sched_sim)
            if use_status:
                return use_status
            return self.direction_start_of_drive(sched_sim)
        else:
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
        

    def find_missing_drives(self):
        print("finding missing drives") # ================
        leveldrives = m.SchedSim.objects.filter(scenario=self.scenario).values_list('description', flat=True).distinct()
        leveldrive_list = set(leveldrives)

        scenario_entries = m.SchedSim.objects.filter(scenario=self.scenario)

        for scenario_entry in scenario_entries:
            adjacent_drives = pcm.BlockAdjacency.objects.filter(block=scenario_entry.bogging_block).values_list('adjacent_block__description', flat=True).distinct()

            for adjacent_drive in adjacent_drives:
                if adjacent_drive not in leveldrive_list:
                    # Add missing drive to SchedSim
                    print(f'adding {adjacent_drive} to scenario') # ======================
                    new_entry = m.SchedSim(
                        description=adjacent_drive,
                        scenario=self.scenario,
                        # Populate other necessary fields for the new entry
                        level=scenario_entry.level,
                    )
                    new_entry.save()  # Save the new entry
                    leveldrive_list.add(adjacent_drive)  # Add to set to avoid duplicates in this run


    
    # ================== UNUSED METHODS =====================================
    
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

    def get_bcd_start_points_actual(self, level_list):
        snapshot_now = []
        for level in level_list:
            level_status = {'level': level, 'oredrives': []}
            distinct_drives = pcm.FlowModelConceptRing.objects.filter(
                is_active=True, level=level).values_list('description', flat=True).distinct()
            drives_list = list(distinct_drives)
            od = []
            for drive_desc in drives_list:
                curr_status = self.get_oredrive_status(level, drive_desc)
                od.append(curr_status)
            level_status['oredrives'] = od
            snapshot_now.append(level_status)
        return snapshot_now

    def get_oredrive_status(self, level, drive_desc):
        od = {'name': drive_desc, 'bogging': None, 'charged': None,
              'drilled': None, 'designed': None, 'direction': None}

        drive_actuals = pam.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            concept_ring__description=drive_desc
        )

        # Collect possible states in a single dictionary
        possible_states = {
            'bogging': drive_actuals.filter(status='Bogging'),
            'charged': drive_actuals.filter(status='Charged'),
            'drilled': drive_actuals.filter(status='Drilled'),
            'designed': drive_actuals.filter(status='Designed')
        }

        reference_state = None
        reference_key = None
        comparitor_state = None
        comparitor_key = None
        comparator = False

        for state_name, queryset in possible_states.items():
            if queryset.exists():
                if reference_state is None:
                    reference_state = queryset
                    reference_key = state_name
                else:
                    comparator = True
                    comparitor_state = queryset
                    comparitor_key = state_name
                    od[state_name] = self.get_farthest_ring(
                        reference_state, queryset)
            # find value of reference state
        if comparator:
            od[reference_key] = self.get_closest_ring(
                comparitor_state, reference_state)
            baf = BlockAdjacencyFunctions()
            od['direction'] = baf.determine_direction(
                od[reference_key], od[comparitor_key])
        elif reference_key == 'designed':
            od['designed'], od['direction'] = self.get_last_designed_plus_dir(reference_state)
        return od
    
    def get_last_designed_plus_dir(self, designed_queryset):
        # try to use ring numbers
            reference_ring = None
            reference_num = None
            comparator_ring = None
            comparator_num = None
            for ring in designed_queryset:
                try:
                    ring_num = int(ring.ring_number_txt)
                    if ring_num < 1000:
                        if reference_ring:
                            comparator_ring = ring
                            comparator_num = ring_num
                            baf = BlockAdjacencyFunctions()
                            
                            # Determine the direction based on the comparison
                            if reference_num < comparator_num:
                                dir = baf.determine_direction(reference_ring, comparator_ring)
                            else:
                                dir = baf.determine_direction(comparator_ring, reference_ring)
                            
                            # Get the last ring in the specified direction
                            last_ring = self.get_last_ring_in_direction(designed_queryset, dir)
                            return last_ring, dir
                        else:
                            # Set the reference ring and its number
                            reference_ring = ring
                            reference_num = ring_num
                except ValueError as e:
                    print(f"Error: Unable to convert ring number to integer: {e}")
                    continue
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")
                    continue


    def get_last_ring_in_direction(self, queryset, direction):
        baf = BlockAdjacencyFunctions()
        last_ring = None
        max_distance = 0
        for ring in queryset:
            if not last_ring:
                last_ring = ring
            elif baf.determine_direction(last_ring, ring) == direction:
                last_ring = ring

        return last_ring
                        


    def get_farthest_ring(self, these_rings, those_rings):
        """
        Input: ProdRing querysets
        Output: FlowConcept block
        """
        if not these_rings.exists() or not those_rings.exists():
            return None

        this_ring = these_rings.first()
        baf = BlockAdjacencyFunctions()
        farthest_ring = None
        max_distance = 0
        for ring in those_rings:
            distance = baf.get_dist_to_block(this_ring, ring)
            if distance > max_distance:
                max_distance = distance
                farthest_ring = ring
        return farthest_ring.concept_ring if farthest_ring else None

    def get_closest_ring(self, these_rings, those_rings):
        """
        Input: ProdRing querysets
        Output: FlowConcept block
        """
        if not these_rings.exists() or not those_rings.exists():
            return None

        this_ring = these_rings.first()
        baf = BlockAdjacencyFunctions()
        closest_ring = None
        min_distance = 10000
        for ring in those_rings:
            distance = baf.get_dist_to_block(this_ring, ring)
            if distance < min_distance:
                max_distance = distance
                closest_ring = ring
        return closest_ring.concept_ring if closest_ring else None

    def marry_designed_rings(self):
        pass

    def direction_use_adjacent_dir(self, sched_sim):
        current_block = sched_sim.bogging_block
        adjacent_blocks = pcm.BlockAdjacency.objects.filter(
            block=current_block)
        adj_same_drive = [
            (block.adjacent_block, block.direction)
            for block in adjacent_blocks
            if block.adjacent_block.description == current_block.description]
        for adj_block in adj_same_drive:
            adj = m.SchedSim.objects.filter(
                scenario=self.scenario, blastsolids_id=adj_block.blastsolids_id)
            if adj:
                if adj.mining_direction:
                    return adj.mining_direction
        return None