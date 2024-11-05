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
        self.scenario = m.Scenario.objects.get(scenario=37)

    def handle_schedule_file(self, request, file, scenario_name):
        user = request.user

        # Create a new Scenario instance
        # scenario = m.Scenario.objects.create(
        #     name=scenario_name,
        #     owner=user,
        #     datetime_stamp=timezone.now()
        # )
        # self.scenario = scenario

        # Process the uploaded CSV file
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
        Read the CSV file and create ScheduleSimulator entries for each row.
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

            # Create a ScheduleSimulator object for each row
            m.ScheduleSimulator.objects.create(
                concept_ring=None,  # Assuming you'll handle concept_ring logic separately
                production_ring=None,  # Assuming you'll handle production_ring logic separately
                scenario=self.scenario,
                description=row.get(required_columns.get("name", ''), ''),
                blastsolids_id=row.get(required_columns.get("id", ''), ''),
                start_date=start_date,
                finish_date=finish_date,
                level=int(row.get(required_columns.get("level", ''), 0)),
                x=row.get(required_columns.get("x", 0), 0),
                y=row.get(required_columns.get("y", 0), 0),
                z=row.get(required_columns.get("z", 0), 0),
                json={},  # Handle json field if required
            )

            rows_processed += 1

        return rows_processed

    def run_scenario(self):
        # Get distinct levels within the specified scenario
        distinct_levels = m.ScheduleSimulator.objects.filter(
            scenario=self.scenario).values_list('level', flat=True).distinct()
        level_list = list(distinct_levels)
        print('levels list', level_list)  # ============
        start_state = self.get_bcd_start_points_actual(level_list)
        print(start_state)  # ======================
        distinct_months = m.ScheduleSimulator.objects.filter(scenario=self.scenario).annotate(
            year=ExtractYear('start_date'),
            month=ExtractMonth('start_date')
        ).values('year', 'month').distinct().order_by('year', 'month')

        for entry in distinct_months:
            year = entry['year']
            month = entry['month']

            # Filter ScheduleSimulator records for the current (year, month) and scenario
            records_in_month = m.ScheduleSimulator.objects.filter(
                scenario=self.scenario,
                start_date__year=year,
                start_date__month=month
            )

            # Process records_in_month as needed
            for record in records_in_month:
                # Your processing logic here
                pass

    def get_bcd_start_points_actual(self, level_list):
        snapshot_now = []
        for level in level_list:
            print('working on level:', level)  # ===================
            level_status = {'level': level, 'oredrives': []}
            distinct_drives = pcm.FlowModelConceptRing.objects.filter(
                is_active=True, level=level).values_list('description', flat=True).distinct()
            drives_list = list(distinct_drives)
            od = []
            for drive_desc in drives_list:
                print('working on od:', drive_desc)  # ================
                od.append(self.get_oredrive_status(level, drive_desc))
            level_status['oredrives'] = od
            snapshot_now.append(level_status)
        return snapshot_now

    def get_oredrive_status(self, level, drive_desc):
        od = {'bogging': None, 'charged': None,
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
        comparator = False

        for state_name, queryset in possible_states.items():
            print('working on:', state_name)  # =============
            if queryset.exists():
                # =====
                for r in queryset:
                    print(r)  # ============
                if reference_state is None:
                    reference_state = queryset
                    reference_key = state_name
                else:
                    comparator = True
                    od[state_name] = self.get_farthest_ring(
                        reference_state, queryset)
            # find value of reference state
        if comparator:
            print('doing comparisons', comparator)  # ==============
            od[reference_key] = self.get_closest_ring(
                queryset, reference_state)
            baf = BlockAdjacencyFunctions()
            # =============
            print('getting direction', od[reference_key], od[state_name])
            od['direction'] = baf.determine_direction(
                od[reference_key], od[state_name])
        print(od)  # ===============
        return od

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

    def marry_concept_rings(self):
        sched_to_marry = m.ScheduleSimulator.objects.filter(
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
            sched_block.concept_ring = concept_block
            updated_sched_blocks.append(sched_block)

        # Use bulk_update to save all changes at once
        m.ScheduleSimulator.objects.bulk_update(
            updated_sched_blocks, ['concept_ring'])

    def populate_mining_direction(self):
        to_update = m.ScheduleSimulator.objects.filter(scenario=self.scenario)
        updated_blocks = []

        for sched_block in to_update:
            print(sched_block.description)  # ===
            direction = self.calc_mining_direction(sched_block, self.scenario)
            print("Direction", direction)  # ===================
            sched_block.mining_direction = direction
            updated_blocks.append(sched_block)

        # Perform a bulk update on mining_direction
        m.ScheduleSimulator.objects.bulk_update(
            updated_blocks, ['mining_direction'])

    def calc_mining_direction(self, sched_sim):
        # Sched_sim, yeah i know, its a shit name for a simulated scheduled block.. but what to do?

        if self.is_block_in_flow_concept(sched_sim):
            print("trying schedule dates")
            use_dates = self.direction_check_sched_dates(sched_sim)
            if use_dates:
                print("used dates from schedule")  # =====================
                return use_dates
            use_status = self.direction_check_status(sched_sim)
            if use_status:
                return use_status
            # =====================
            print("used count direction from start of drive")
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

    def direction_use_adjacent_dir(self, sched_sim):
        current_block = sched_sim.concept_ring
        adjacent_blocks = pcm.BlockAdjacency.objects.filter(
            block=current_block)
        adj_same_drive = [
            (block.adjacent_block, block.direction)
            for block in adjacent_blocks
            if block.adjacent_block.description == current_block.description]
        for adj_block in adj_same_drive:
            adj = m.ScheduleSimulator.objects.filter(
                scenario=self.scenario, blastsolids_id=adj_block.blastsolids_id)
            if adj:
                if adj.mining_direction:
                    return adj.mining_direction
        return None

    def direction_check_sched_dates(self, sched_sim):
        sched_same_drive = m.ScheduleSimulator.objects.filter(
            is_active=True,
            scenario=self.scenario,
            description=sched_sim.description
        )
        if sched_same_drive.count() > 1:
            current_block = sched_sim.concept_ring
            ba = BlockAdjacencyFunctions()

            for block_same_drv in sched_same_drive:
                if ba.is_adjacent(current_block, block_same_drv.concept_ring):
                    current_block_date = sched_sim.start_date
                    block_same_drv_date = block_same_drv.start_date

                    if current_block_date < block_same_drv_date:
                        direction = ba.determine_direction(
                            current_block, block_same_drv.concept_ring)
                    elif current_block_date == block_same_drv_date:
                        continue
                    else:
                        direction = ba.determine_direction(
                            block_same_drv.concept_ring, current_block)
                    return direction
        else:
            return None

    def direction_check_status(self, sched_sim):
        current_block = sched_sim.concept_ring
        actuals = pam.ProductionRing.objects.filter(
            is_active=True, concept_ring=current_block)

        adjacent_blocks = pcm.BlockAdjacency.objects.filter(
            block=current_block)
        adj_same_drive = [
            (block.adjacent_block, block.direction)
            for block in adjacent_blocks
            if block.adjacent_block.description == current_block.description]

        if actuals:
            s = Status()
            st1 = actuals.first()
            status1 = st1.status
            pos1 = s.get_position(status1)

            for adj_block, direction in adj_same_drive:
                pos_change = 0
                has_skipped_a_block = False
                while pos_change == 0:
                    rings = pam.ProductionRing.objects.filter(
                        is_active=True, concept_ring=adj_block)

                    if rings:
                        pos2 = s.get_position(rings.first().status)
                        pos_change = pos1 - pos2
                        if pos_change > 0:
                            return direction
                        elif pos_change < 0:
                            return self.opposite_direction[direction]
                    else:
                        if has_skipped_a_block:
                            return direction
                        else:
                            has_skipped_a_block = True

                    # Retrieve the next adjacent block in the same direction
                    next_block_adj = pcm.BlockAdjacency.objects.filter(
                        block=adj_block, direction=direction
                    ).first()  # Get the first matching adjacency

                    if next_block_adj:
                        adj_block = next_block_adj.adjacent_block
                    else:
                        # End of drive or no further adjacency in this direction
                        pos_change = 1
        return None

    def direction_start_of_drive(self, sched_sim):
        # Nothing designed, we are close to start of drive
        current_block = sched_sim.concept_ring
        adjacent_blocks = pcm.BlockAdjacency.objects.filter(
            block=current_block)
        adj_same_drive = [
            (block.adjacent_block, block.direction)
            for block in adjacent_blocks
            if block.adjacent_block.description == current_block.description
        ]
        first_count = 0
        for adj_block, direction in adj_same_drive:
            if len(adj_same_drive) == 1:  # Use len() to get the length of the list
                return direction
            else:
                # Start counting blocks
                count = 0
                end_of_drive = False
                while not end_of_drive:
                    next_block = pcm.BlockAdjacency.objects.filter(
                        block=adj_block, direction=direction
                    ).first()
                    if next_block:
                        adj_block = next_block.adjacent_block  # Access the adjacent_block field
                        count += 1
                    else:
                        first_count = count
                        end_of_drive = True
        if first_count > count:
            return direction
        else:
            return self.opposite_direction[direction]

    def get_levels_list(self):
        levels = m.ScheduleSimulator.objects.filter(
            is_active=True, scenario=self.scenario).values_list('level', flat=True).distinct()

        return list(levels)
