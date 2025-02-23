from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, IntegrityError
from django.db.models import Sum

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from prod_actual.models import ProductionRing, BoggedTonnes
from common.functions.common_methods import CommonMethods

from datetime import timedelta, date

import report.models as m
import json


class LevelStatusReportView(APIView):
    def get(self, request, *args, **kwargs):
        lsr = LevelStatusReport()
        report = lsr.fetch_ls_report()
        return Response(report, status=status.HTTP_200_OK)


class LevelStatusReport():
    def __init__(self) -> None:
        self.active_levels = set()
        self.active_drives = []

        # shared attributes
        self.level = None
        self.oredrive = None
        self.ring = None

    def fetch_ls_report(self):
        try:
            report = m.JsonReport.objects.filter(
                name="Prod Level Status Report").latest('datetime_stamp')
            return report.report

        except m.JsonReport.DoesNotExist:
            # Return an empty JSON object if the report does not exist
            print("No level status report.. generating")
            report = self.create_ls_report()
            return report

        except DatabaseError as e:
            # Handle database errors
            print(f"Database error occurred: {str(e)}")
            return {"msg": "Database error"}

        except Exception as e:
            # Catch all other exceptions
            print(f"An error occurred: {str(e)}")
            return {"msg": "An error occurred"}

    def create_ls_report(self, for_date="20241005P1"):
        try:
            report = self.list_active_rings()

            m.JsonReport.objects.create(
                name="Prod Level Status Report",
                report=report,
                for_date=for_date,
            )
            print("Report successfully saved.")
        except IntegrityError as e:
            # Handle integrity issues, such as violating unique constraints
            print(f"Integrity error occurred: {str(e)}")
        except DatabaseError as e:
            # Handle general database errors
            print(f"Database error occurred: {str(e)}")
        except Exception as e:
            # Catch any other exceptions
            print(f"An error occurred: {str(e)}")

    def delete_ls_report(self):
        # this only happens when updating report
        pass

    def list_active_rings(self):
        # Step 1: Query the data
        current_rings = ProductionRing.objects.filter(status='Bogging').values(
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
        drilled = []
        charged = []
        bogging = {'overdraw_tonnes': 0, 'bogged_tonnes': 0,
                   'overdraw_zone': '', 'comment': '', 'in_flow': None}
        designed = {'rings': 0, 'mtrs': 0}
        designed_tonnes = 0
        primary_ring = None
        latest_drilled_ring = None

        od_rings = ProductionRing.objects.filter(
            level=level, oredrive=oredrive)

        for self.ring in od_rings:
            if self.ring.status == 'Designed':
                designed['rings'] += 1
                designed['mtrs'] += self.ring.drill_meters

            elif self.ring.status == 'Drilled':

                #TODO: Fix this ===============================
                '''
                if self.ring.has_blocked_holes:
                    drilled.append(
                        {"ring": self.ring.ring_number_txt, "is_blocked": self.ring.has_blocked_holes})'''

                if latest_drilled_ring is None or self.ring.drill_complete_shift > latest_drilled_ring.drill_complete_shift:
                    latest_drilled_ring = self.ring

            elif self.ring.status == 'Charged':
                osr_state = self.is_overslept_ring()
                charged.append({'ring': self.ring.ring_number_txt,
                               'detonator': self.ring.detonator_actual, 'fireby_date': self.ring.fireby_date, 'is_overslept': osr_state})

            elif self.ring.status == 'Bogging':
                designed_tonnes += self.ring.designed_tonnes
                if self.ring.multi_fire_group != '(M)':
                    primary_ring = self.ring

        '''
        if latest_drilled_ring:
            # Ensure it's not already in the list
            if latest_drilled_ring.ring_number_txt not in [ring["ring"] for ring in drilled]:
                drilled.append({"ring": latest_drilled_ring.ring_number_txt,
                               "is_blocked": latest_drilled_ring.has_blocked_holes})'''

        bogging = self.calculate_bogging_ring(primary_ring, designed_tonnes)

        drive['name'] = oredrive
        drive['designed'] = designed
        drive['drilled'] = drilled
        drive['charged'] = charged
        drive['bogging'] = bogging

        return drive

    def calculate_bogging_ring(self, primary_ring, designed_tonnes):
        cm = CommonMethods()
        bogging = {}

        # get designed tonnes
        if primary_ring.in_flow:
            try:
                bogging['designed_tonnes'] = primary_ring.concept_ring.pgca_modelled_tonnes
            except AttributeError:
                bogging['comment'] = "ORPHANED FLOW RING"
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
        print("bogged", bogging['bogged_tonnes'])  # ===============
        bogging['overdraw_zone'] = primary_ring.in_overdraw_zone
        bogging['overdraw_tonnes'] = cm.no_null(primary_ring.overdraw_amount)
        bogging['in_flow'] = primary_ring.in_flow
        bogging['comment'] = (str(bogging.get(
            'comment', '') or '') + ' ' + str(primary_ring.comment or '')).strip()
        bogging['draw_ratio'] = primary_ring.draw_percentage
        bogging['draw_deviation'] = cm.no_null(primary_ring.draw_deviation)

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
        result = BoggedTonnes.objects.filter(production_ring=ring).aggregate(
            total_bogged_tonnes=Sum('bogged_tonnes'))

        # result will be a dictionary with 'total_bogged_tonnes' key, return the value or 0 if None
        return result['total_bogged_tonnes'] or 0

    def is_overslept_ring(self):
        # charge_date is a string in the format yyyy-mm-dd
        if not self.ring.charge_shift:
            return False

        charge_date = date.fromisoformat(self.ring.charge_shift)
        overslept_date = charge_date + timedelta(days=28)

        return date.today() > overslept_date
