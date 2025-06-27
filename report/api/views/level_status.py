from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, IntegrityError
from django.db.models import Sum

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.functions.common_methods import CommonMethods
from common.functions.shkey import Shkey

from datetime import timedelta, datetime, date
from itertools import groupby
from operator import attrgetter

import report.models as m
import prod_actual.models as pm
import json


class LevelStatusReportView(APIView):
    def get(self, request, *args, **kwargs):
        lsr = LevelStatusReport()
        report = lsr.fetch_ls_report()
        return Response(report, status=status.HTTP_200_OK)


class LevelStatusCreateReportView(APIView):
    def get(self, request, *args, **kwargs):
        # Read “draft” from query params (default to "false" if not provided)
        draft_param = request.query_params.get('draft', 'false').lower()
        is_draft = draft_param in ('true', '1')

        # Instantiate your report and set the flag
        lsr = LevelStatusReport()
        lsr.is_draft = is_draft

        # Call whatever logic generates/saves your report
        reply = lsr.create_ls_report(request)

        return Response(reply, status=status.HTTP_200_OK)


class LevelStatusReport():
    def __init__(self) -> None:
        self.active_levels = set()
        self.active_drives = []
        self.is_draft = None

        # shared attributes
        self.level = None
        self.oredrive = None
        self.sleep_days = 28  # days after which a ring is considered overslept

    def fetch_ls_report(self):
        try:
            report = m.JsonReport.objects.filter(
                name="Prod Level Status Report").latest('datetime_stamp')
            return report.report

        except m.JsonReport.DoesNotExist:
            # Return an empty JSON object if the report does not exist
            return {'msg': {'body': 'Report not generated yet', 'type': 'warning'}}

        except DatabaseError as e:
            # Handle database errors
            print(f"Database error occurred: {str(e)}")
            return {"msg": {'body': "Database error", 'type': 'error'}}

        except Exception as e:
            # Catch all other exceptions
            print(f"An error occurred: {str(e)}")
            return {"msg": {'body': "An error occurred", 'type': 'error'}}

    def create_ls_report(self, request):
        print("request", request.user)
        right_now = Shkey.today_shkey()

        def get_current_shift():
            hour = datetime.now().hour
            return "Nightshift" if hour >= 12 else "Dayshift"

        try:
            ls_report = self.list_active_rings()
            report_date_str = datetime.now().strftime('%d/%m/%Y %I:%M %p')
            shift = get_current_shift()

            report = {
                'author': {
                    "full_name": request.user.get_full_name() if request.user else "Anonymous User",
                    "avatar": request.user.avatar,
                    "initials": request.user.initials if request.user else None,
                } if request.user else None,

                'report_date': report_date_str,
                'shift': shift,
                'report': ls_report,
                'is_draft': self.is_draft
            }
            self.delete_ls_report()

            m.JsonReport.objects.create(
                name="Prod Level Status Report",
                report=report,
                for_date=right_now,
            )
            return {'msg': {'body': "Report created successfully", 'type': 'success'}}

        except IntegrityError as e:
            print(f"Integrity error occurred: {str(e)}")
            return {'msg': {'body': 'Integrity error occurred', 'type': 'error'}}
        except DatabaseError as e:
            print(f"Database error occurred: {str(e)}")
            return {'msg': {'body': 'Database error occurred', 'type': 'error'}}
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return {'msg': {'body': 'An error occurred', 'type': 'error'}}

    def delete_ls_report(self):
        m.JsonReport.objects.filter(name="Prod Level Status Report").delete()

    def list_active_rings(self):
        # Step 1: Query the data
        current_rings = pm.ProductionRing.objects.filter(is_active=True, status='Bogging').values(
            'level', 'oredrive').distinct().order_by('level', 'oredrive')

        # Step 2: Structure the data by levels
        report_data = []
        level_data = {}

        for ring in current_rings:
            level = ring['level']
            oredrive = ring['oredrive']

            # Check if the current level is already in level_data
            if level not in level_data:
                # If not, initialize a new object for the level
                level_data[level] = {
                    'level': level,
                    'ore_drives': []
                }
                report_data.append(level_data[level])

            # Append the oredrive status to the 'ore_drives' array
            level_data[level]['ore_drives'].append(
                self.oredrive_status(level, oredrive))

        # Step 3: Convert the structured data to JSON
        report_json = json.dumps(report_data, cls=DjangoJSONEncoder, indent=4)

        return report_json

    def oredrive_status(self, level, oredrive):
        drive = {}

        od_rings = pm.ProductionRing.objects.filter(
            is_active=True, level=level, oredrive=oredrive).order_by('status')

        for status, group in groupby(od_rings, key=attrgetter('status')):
            rings = list(group)

            if status == 'Designed':
                drive['designed'] = self.handle_designed(rings)
            elif status == 'Drilled':
                drive['drilled'] = self.handle_drilled(rings)
            elif status == 'Charged':
                drive['charged'] = self.handle_charged(rings)
            elif status == 'Bogging':
                drive['bogging'] = self.handle_bogging(rings)
            elif status == 'Complete':
                # I dont care about this right now, maybe later
                pass
            else:
                # other, maybe later as well
                print(status)

        drive['name'] = oredrive

        return drive

    def handle_designed(self, rings):
        designed = {'rings': 0, 'mtrs': 0}
        for ring in rings:
            designed['rings'] += 1
            if ring.drill_meters:
                designed['mtrs'] += ring.drill_meters
        return designed

    def handle_drilled(self, rings):
        drilled = {'last_drilled': None, 'problem_rings': []}
        sorted_rings = sorted(
            rings, key=lambda r: r.drill_complete_shift or "")
        for ring in sorted_rings:
            drilled['last_drilled'] = ring.ring_number_txt
            prob = pm.RingStateChange.objects.filter(
                is_active=True, prod_ring=ring, state__pri_state='Drilled', state__sec_state='Blocked Holes')
            for p in prob:
                drilled['problem_rings'].append(
                    {'ring_number_txt': ring.ring_number_txt, 'condition': 'Blocked Holes'})

        return drilled

    def handle_charged(self, rings):
        charged = []
        for ring in rings:
            osr_state = self.is_overslept_ring(ring)
            charged.append({'ring': ring.ring_number_txt, 'detonator': ring.detonator_actual,
                           'fireby_date': ring.fireby_date, 'is_overslept': osr_state})

        return charged

    def handle_bogging(self, rings):
        designed_tonnes = 0
        primary_ring = None

        for ring in rings:
            designed_tonnes += ring.designed_tonnes

            if ring.multi_fire_group != '(M)':
                primary_ring = ring

        bogging = self.calculate_bogging_ring(primary_ring, designed_tonnes)

        return bogging

    def calculate_bogging_ring(self, primary_ring, designed_tonnes):
        cm = CommonMethods()
        bogging = {}

        # get designed tonnes
        if primary_ring.in_flow:
            try:
                bogging['designed_tonnes'] = primary_ring.concept_ring.pgca_modelled_tonnes
            except AttributeError:
                bogging['comment'] = "ORPHANED RING"
        else:
            bogging['designed_tonnes'] = designed_tonnes

        # get name
        if primary_ring.multi_fire_group:
            if primary_ring.multi_fire_group in ['(MP)', '(M)']:
                bogging['ring_txt'] = primary_ring.ring_number_txt
            else:
                bogging['ring_txt'] = primary_ring.multi_fire_group
        else:
            bogging['ring_txt'] = primary_ring.ring_number_txt

        bogging['bogged_tonnes'] = self.get_bogged_tonnes(primary_ring)
        bogging['overdraw_zone'] = primary_ring.in_overdraw_zone
        bogging['overdraw_tonnes'] = cm.no_null(primary_ring.overdraw_amount)
        bogging['in_flow'] = primary_ring.in_flow
        bogging['comment'] = (str(bogging.get(
            'comment', '') or '') + ' ' + str(primary_ring.comment or '')).strip()
        bogging['draw_ratio'] = primary_ring.draw_percentage
        bogging['draw_deviation'] = cm.no_null(primary_ring.draw_deviation)
        bogging['conditions'] = self.get_ring_conditions(primary_ring)

        overdraw_tonnes = bogging['overdraw_tonnes']
        bogged_tonnes = bogging['bogged_tonnes']
        draw_ratio = bogging['draw_ratio']
        deviation = bogging['draw_deviation']

        avail_tonnes = (deviation + overdraw_tonnes +
                        (designed_tonnes * draw_ratio)) - bogged_tonnes

        bogging['avail_tonnes'] = avail_tonnes

        if avail_tonnes < 0:
            bogging['is_overbogged'] = True
        else:
            bogging['is_overbogged'] = False

        return bogging

    def get_bogged_tonnes(self, ring):
        result = pm.BoggedTonnes.objects.filter(production_ring=ring).aggregate(
            total_bogged_tonnes=Sum('bogged_tonnes'))

        # result will be a dictionary with 'total_bogged_tonnes' key, return the value or 0 if None
        return result['total_bogged_tonnes'] or 0

    def is_overslept_ring(self, ring):
        # charge_shift is a shkey
        if not ring.charge_shift:
            return False
        charge_date = date.fromisoformat(ring.charge_shift)
        overslept_date = charge_date + timedelta(days=self.sleep_days)

        return date.today() > overslept_date

    def get_ring_conditions(self, ring):
        cond_list = []
        active_cond = pm.RingStateChange.objects.filter(
            is_active=True, prod_ring=ring)

        for c in active_cond:
            condition = c.state.sec_state
            if condition:  # skips None, '', 0, and other falsy values
                cond_list.append(condition)

        return cond_list
