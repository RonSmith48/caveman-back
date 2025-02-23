from rest_framework import generics, status
from rest_framework.response import Response

import whatif.api.serializers as s
import whatif.models as m
import prod_concept.models as pcm
import prod_actual.models as pam

from common.functions.status import Status
from common.functions.block_adjacency import BlockAdjacencyFunctions
from settings.models import ProjectSetting
from prod_concept.api.views.mining_direction import MiningDirectionView

from time import strftime
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import transaction
from django.db.models import Sum, F, Q, ExpressionWrapper, Min
from django.db.models.functions import Abs, ExtractMonth, ExtractYear
from datetime import datetime, timedelta
from decimal import Decimal
from pprint import pprint
from copy import deepcopy

import csv
import calendar
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
        self.assumed_mtrs_in_start_drive = 900
        self.assumed_rings_in_start_drive = 10

        self.ring_count = 0
        self.meter_count = 0

        self.scenario = None
        # self.scenario = m.Scenario.objects.get(scenario=38)

        # counting drill mtrs / rings
        self.last_designed_block = None
        self.is_designed = False
        self.reporting_interval = 'monthly'
        self.filename = 'results.csv'
        self.split_month = False

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
            return {'msg': {'body': self.error_msg, 'type': 'error'}}

        print("marrying concept rings")
        self.marry_concept_rings()
        if self.error_msg:
            return {'msg': {'body': self.error_msg, 'type': 'error'}}
        print("Running the scenario")
        self.run_scenario()
        if self.error_msg:
            return {'msg': {'body': self.error_msg, 'type': 'error'}}

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
                self.error_msg = f'Unreadable start date at line {
                    rows_processed}'
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

        print("calculating charged blocks")
        for sched_item in all_sched:
            try:
                concept_ring = m.FlowModelConceptRing.objects.get(
                    blastsolids_id=sched_item.blastsolids_id)
            except m.FlowModelConceptRing.DoesNotExist:
                self.error_msg = f'Block with ID:{
                    sched_item.blastsolids_id} is not in the database.'
                return
            drv_name = self.determine_mining_direction(concept_ring)
            if not drv_name:
                return

            sched_item.description = drv_name
            sched_item.last_charge_block = self.calc_last_charged_block(
                sched_item)
            sched_item.save()

        print("populate last drill block")
        self.populate_last_drill_block()
        if self.error_msg:
            print("error", self.error_msg)
            return

        print("calc drill rings and meters")  # ========
        self.calculate_drill_sums()
        if self.error_msg:
            print("error", self.error_msg)
            return

        self.generate_schedule_csv()

    def determine_mining_direction(self, concept_ring):
        drv_name = self.mining_dir_successor_method(concept_ring)
        if drv_name:
            return drv_name
        else:
            print("guessing mining direction")
            return self.mining_dir_guess_method(concept_ring)

    def mining_dir_successor_method(self, concept_ring):
        baf = BlockAdjacencyFunctions()
        drv_name = concept_ring.description
        links = pcm.BlockLink.objects.filter(block=concept_ring)
        if links:
            for link in links:
                if link.linked.description == drv_name:
                    if link.direction == 'S':
                        self.mining_direction = baf.determine_direction(
                            concept_ring, link.linked)
                    else:
                        self.mining_direction = baf.determine_direction(
                            link.linked, concept_ring)
                    return drv_name
        return None


    def mining_dir_guess_method(self, concept_ring):
        # if there is an alias, try to use that first
        drv_name = concept_ring.alias
        if drv_name:
            direction = pcm.MiningDirection.objects.filter(
                description=drv_name).first()
            if direction:
                self.mining_direction = direction.mining_direction
                return drv_name

        drv_name = concept_ring.description
        if drv_name:
            direction = pcm.MiningDirection.objects.filter(
                description=drv_name).first()
            if direction:
                self.mining_direction = direction.mining_direction
                return drv_name
        self.error_msg = f'There is no mining direction for oredrive {
            drv_name}, fix it and try again.'
        print(self.error_msg)
        return None

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
            if not concept_block:
                self.error_msg = f'Unknown blastsolid: {
                    sched_block.blastsolids_id}'
                print(self.error_msg)
                return

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
            charged = baf.step_dist_using_successor_method(sched_item.bogging_block, self.min_precharge_amount)

        if sched_item.description:
            # might already be charged past calc pos
            last_charged_block = self.get_current_last_block_of_status(
                sched_item.description, 'Charged')
        if charged:
            if last_charged_block:
                if last_charged_block != charged:
                    if baf.is_in_general_mining_direction(sched_item.bogging_block, last_charged_block, self.mining_direction):
                        return last_charged_block
            return charged
        return None

    def get_current_last_block_of_status(self, description, status):
        baf = BlockAdjacencyFunctions()
        designed_rings = pam.ProductionRing.objects.filter(
            is_active=True, status=status, concept_ring__description=description)
        if not designed_rings:
            # could be using alias
            designed_rings = pam.ProductionRing.objects.filter(
                is_active=True, status=status, description=description)
        if designed_rings:
            last_ring = baf.get_last_block_in_set(
                designed_rings, self.mining_direction)
            return last_ring.concept_ring
        else:
            return None

    def get_last_designed_block(self, description):
        baf = BlockAdjacencyFunctions()
        designed_rings = pam.ProductionRing.objects.filter(
            is_active=True, concept_ring__description=description)
        if designed_rings:
            last_ring = baf.get_last_block_in_set(
                designed_rings, self.mining_direction)
            return last_ring.concept_ring
        else:
            return None

    def populate_last_drill_block(self):
        baf = BlockAdjacencyFunctions()
        oredrive_list = m.SchedSim.objects.filter(
            scenario=self.scenario).values_list('description', flat=True).distinct()
        for oredrive in oredrive_list:
            sched_by_drive = m.SchedSim.objects.filter(
                scenario=self.scenario, description=oredrive).order_by('start_date')
            # set mining direction
            first_block = sched_by_drive.first().bogging_block
            self.mining_direction = self.mining_dir_successor_method(first_block)
            
            current_drilled = self.get_current_last_block_of_status(
                oredrive, 'Drilled')

            for sched_item in sched_by_drive:
                sched_item.last_drill_block = current_drilled
                sched_item.save()
                if sched_item.last_charge_block:
                    self.add_min_drilling(sched_item)
                    eod = baf.get_last_block_in_drive(
                        sched_item.description, self.mining_direction)
                    if sched_item.last_drill_block and sched_item.last_drill_block != eod:
                        self.interference_from_others(sched_item, eod)
                    self.interfere_with_others(sched_item)

    def add_min_drilling(self, sched_item):
        baf = BlockAdjacencyFunctions()
        if sched_item.last_charge_block:
            min_drill = baf.step_dist(
                sched_item.last_charge_block, self.mining_direction, self.min_amount_drilled)
            if min_drill:
                if sched_item.last_drill_block:
                    if baf.is_in_general_mining_direction(sched_item.last_drill_block, min_drill, self.mining_direction):
                        sched_item.last_drill_block = min_drill
                        sched_item.save()
                else:
                    sched_item.last_drill_block = min_drill
                    sched_item.save()
            else:
                # no min drill means we have exceeded eod
                sched_item.last_drill_block = None
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
                    dist = baf.get_dist_to_block(
                        sched_item.last_drill_block, adj_charged)
                    drill = sched_item.last_drill_block
                    while dist < self.min_amount_drilled and drill != eod:
                        # get interfered with
                        next_block = baf.step_next_block(
                            drill, self.mining_direction)
                        if next_block:
                            drill = next_block
                    sched_item.last_drill_block = drill
                    sched_item.save()

    def interfere_with_others(self, sched_item):
        # now for the fun stuff
        baf = BlockAdjacencyFunctions()
        
        # get adjacent blocks not in same oredrive
        adjacent_blocks = (
            pcm.BlockAdjacency.objects
            .filter(block=sched_item.last_charge_block)  # Get adjacent blocks
            .exclude(adjacent_block__description=sched_item.last_charge_block.description)  # Exclude current oredrive
        )

        # Get distinct oredrives with at least one block from each
        distinct_adjacent_blocks = (
            adjacent_blocks
            .values('adjacent_block__description')  # Group by oredrive description
            .annotate(block_id=Min('adjacent_block__location_id'))  # Pick the smallest ID as a representative
        )

        # Get the actual block objects using the selected block IDs
        selected_blocks = pcm.BlockAdjacency.objects.filter(
            id__in=[desc['block_id'] for desc in distinct_adjacent_blocks]
        )

        # If no adjacent blocks exist, return None
        selected_blocks = list(selected_blocks) if selected_blocks.exists() else None

        if selected_blocks is None:
            return None

        for sb in selected_blocks:
            adj_drive = sb.description
            adj_mining_dir = self.mining_dir_successor_method(sb)
            adj_block = sb
            adj_schedsim = self.get_adj_schedsim(adj_drive, sched_item)
            drill_1 = baf.step_dist(
                adj_block, adj_mining_dir, self.min_amount_drilled)
            # might be in production
            bogging_block = self.get_current_last_block_of_status(
                adj_drive, 'Bogging')
            charged_block = self.get_current_last_block_of_status(
                adj_drive, 'Charged')
            drill_2 = self.get_current_last_block_of_status(
                adj_drive, 'Drilled')
            if drill_1 and drill_2:
                if baf.is_in_general_mining_direction(drill_1, drill_2, adj_mining_dir):
                    drill = drill_2
                else:
                    drill = drill_1
            else:
                drill = drill_1

            if bogging_block == drill or charged_block == drill:
                drill = None

            if not adj_schedsim:
                blastsolid = None
                if bogging_block:
                    blastsolid = bogging_block.blastsolids_id
                # might have nothing, needs drilling
                adj_schedsim = m.SchedSim.objects.create(
                    bogging_block=bogging_block,
                    last_charge_block=charged_block,
                    last_drill_block=drill,
                    scenario=self.scenario,
                    description=adj_drive,
                    start_date=sched_item.start_date,
                    level=sched_item.level,
                    blastsolids_id=blastsolid,
                    json={},
                )
                adj_schedsim.save()

                adj_schedsim.last_charge_block = self.calc_last_charged_block(
                    adj_schedsim)
                adj_schedsim.save()

            if adj_schedsim.bogging_block == drill or adj_schedsim.last_charge_block == drill:
                adj_schedsim.last_drill_block = None
                adj_schedsim.save()
                drill = None

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
                    in_mining_dir = baf.is_in_general_mining_direction(
                        drill, adj_schedsim.last_drill_block, adj_mining_dir)
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
                    level=sched_item.level,
                    blastsolids_id=adj_schedsim.blastsolids_id,
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

    # ============== COUNTING METHODS =====================

    def calculate_drill_sums(self):
        baf = BlockAdjacencyFunctions()
        drives = m.SchedSim.objects.filter(scenario=self.scenario).values_list(
            'description', flat=True).distinct()

        for drive in drives:
            drive_schedule = m.SchedSim.objects.filter(
                scenario=self.scenario, description=drive).order_by('start_date')
            # set mining direction
            md = pcm.MiningDirection.objects.filter(description=drive).first()
            if md:
                self.mining_direction = md.mining_direction
            else:
                self.error_msg = f'No mining direction found for {
                    drive} (Drill sums)'
                print(self.error_msg)
                continue
            self.last_designed_block = self.get_last_designed_block(drive)
            last_drilled = self.get_current_last_block_of_status(
                drive, 'Drilled')
            prev_schedule_block = None

            for sched in drive_schedule:
                if sched.last_drill_block:
                    if prev_schedule_block:
                        self.get_blocks_between(prev_schedule_block, sched)
                        prev_schedule_block = sched.last_drill_block
                    else:
                        if last_drilled:
                            self.get_blocks_between(last_drilled, sched)
                            prev_schedule_block = sched.last_drill_block
                        else:
                            # no previous drilled, is start of drive
                            first_block = baf.find_first_block(
                                drive, self.mining_direction)
                            self.get_blocks_between(
                                first_block, sched, count_first=True)
                            prev_schedule_block = sched.last_drill_block
        print("finished")#================

    def get_blocks_between(self, start_block, sched_item, count_first=False):
        # if start of drive 'Start_block' is None.
        baf = BlockAdjacencyFunctions()
        self.ring_count = 0
        self.meter_count = 0

        self.check_designed(sched_item)

        if not start_block and sched_item.last_drill_block:
            print("not given both blocks", sched_item.description)
            return

        # do sched item counts
        current_block = start_block

        is_correct_dir = baf.is_in_general_mining_direction(
            current_block, sched_item.last_drill_block, self.mining_direction)
        dist = baf.get_dist_to_block(current_block, sched_item.last_drill_block)
        if dist > 50:
            print("Dist too great", current_block.description, sched_item.last_drill_block.description, dist)
            return
        if is_correct_dir:
            while current_block != sched_item.last_drill_block:
                if not count_first:
                    next_block = baf.step_next_block(
                        current_block, self.mining_direction)
                    current_block = next_block

                count_first = False
                if current_block:
                    self.tally(current_block)
                else:
                    print("There was an unexpected end to blocks in drive",
                        sched_item.description)
                    return

        sched_item.sum_drill_rings_from_prev = self.ring_count
        sched_item.sum_drill_mtrs_from_prev = self.meter_count
        sched_item.save()

    def tally(self, current_block):
        rings_in_block = pam.ProductionRing.objects.filter(is_active=True, concept_ring=current_block)
        if rings_in_block:
            for ring in rings_in_block:
                self.ring_count += 1
                self.meter_count += ring.drill_meters
        else:
            self.ring_count += 1
            self.meter_count += self.assumed_mtrs_in_concept_ring

    def check_designed(self, sched):
        baf = BlockAdjacencyFunctions()
        if self.last_designed_block:
            self.is_designed = (sched.last_drill_block == self.last_designed_block or baf.is_in_general_mining_direction(
                sched.last_drill_block, self.last_designed_block, self.mining_direction))
        else:
            self.is_designed = False

    # =============== REPORTING ===================

    def generate_schedule_csv(self):
        print("generating csv")
        queryset = m.SchedSim.objects.filter(
            scenario=self.scenario, start_date__isnull=False)

        # Prepare data aggregation
        data = queryset.values('description', 'start_date', 'start_date__year', 'start_date__month', 'start_date__day') \
            .annotate(
            total_rings=Sum('sum_drill_rings_from_prev'),
            total_mtrs=Sum('sum_drill_mtrs_from_prev')
        ) \
            .order_by('description', 'start_date__year', 'start_date__month', 'start_date__day')

        # Organize data by description and periods (months or half-months)
        descriptions = {}
        for entry in data:
            desc = entry['description']
            year = entry['start_date__year']
            month = entry['start_date__month']
            day = entry['start_date__day']

            # Determine the period based on split_month option
            if self.split_month:
                if day <= 15:
                    period = f"{
                        datetime(year, month, 1).strftime('%b %Y')} (1-15)"
                else:
                    period = f"{datetime(year, month, 16).strftime(
                        '%b %Y')} (16-{calendar.monthrange(year, month)[1]})"
            else:
                period = datetime(year, month, 1).strftime('%b %Y')

            if desc not in descriptions:
                descriptions[desc] = {}
            if period not in descriptions[desc]:
                descriptions[desc][period] = {'rings': 0, 'mtrs': 0}

            descriptions[desc][period]['rings'] += entry['total_rings'] or 0
            descriptions[desc][period]['mtrs'] += entry['total_mtrs'] or 0

        # Get all unique periods and sort them chronologically
        periods = sorted(
            {period for desc_data in descriptions.values()
             for period in desc_data.keys()},
            key=lambda x: datetime.strptime(x.split(" ")[0], '%b').replace(
                year=int(x.split(" ")[1].split("(")[0]))
        )

        # Write to CSV
        with open(self.filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Header rows
            writer.writerow(['Description'] +
                            [period for period in periods for _ in range(2)])
            writer.writerow(
                [''] + [col for period in periods for col in ('Rings', 'Meters')])

            # Data rows
            for desc, period_data in descriptions.items():
                row = [desc]
                for period in periods:
                    if period in period_data:
                        row.append(period_data[period]['rings'])
                        row.append(period_data[period]['mtrs'])
                    else:
                        row.extend([0, 0])  # Fill with zeros if no data
                writer.writerow(row)

            queryset = m.SchedSim.objects.filter(scenario=self.scenario ,start_date__isnull=False)

        data = queryset.values('description', 'start_date__year', 'start_date__month') \
                    .annotate(
                        total_rings=Sum('sum_drill_rings_from_prev'),
                        total_mtrs=Sum('sum_drill_mtrs_from_prev')
                    ) \
                    .order_by('description', 'start_date__year', 'start_date__month')

        # Organize data by description and months
        descriptions = {}
        for entry in data:
            desc = entry['description']
            month = datetime(entry['start_date__year'], entry['start_date__month'], 1).strftime('%b %Y')
            if desc not in descriptions:
                descriptions[desc] = {}
            descriptions[desc][month] = {
                'rings': entry['total_rings'] or 0,
                'mtrs': entry['total_mtrs'] or 0,
            }

        # Get all unique months across data and sort them chronologically
        months = sorted(
            {datetime.strptime(m, '%b %Y') for desc_data in descriptions.values() for m in desc_data.keys()}
        )
        months = [month.strftime('%b %Y') for month in months]

        # Write to CSV
        with open(self.filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header rows
            writer.writerow(['Description'] + [month for month in months for _ in range(2)])
            writer.writerow([''] + [col for month in months for col in ('Rings', 'Meters')])

            # Data rows
            for desc, month_data in descriptions.items():
                row = [desc]
                for month in months:
                    if month in month_data:
                        row.append(month_data[month]['rings'])
                        row.append(month_data[month]['mtrs'])
                    else:
                        row.extend([0, 0])  # Fill with zeros if no data
                writer.writerow(row) 

    # ================ TESTING ====================

    def test_drive_seq(self):
        baf = BlockAdjacencyFunctions()
        drives = m.SchedSim.objects.filter(level=1200).values_list(
            'description', flat=True).distinct()

        for drive in drives:
            mining_direction = pcm.MiningDirection.objects.filter(
                description=drive).first().mining_direction
            first_block = baf.find_first_block(drive, mining_direction)
            print("=====", drive, mining_direction, "=====")
            next_block = first_block

            while next_block:
                print(next_block.location_id, next_block.blastsolids_id)
                next_block = baf.step_next_block(next_block, mining_direction)
