from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.db.models import Sum, F, Value, CharField
from django.db.models.functions import Concat, Cast

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.functions.common_methods import CommonMethods
from common.functions.shkey import Shkey

from datetime import timedelta, date

import prod_actual.models as m
import prod_actual.api.serializers as s
import json


class BoggingRingsView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_bogging_rings(request)
        return Response(rings, status=status.HTTP_200_OK)


class BoggingMovementsView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        bdcf = BDCFRings()
        movements = bdcf.get_bogging_movements(location_id)
        return Response(movements, status=status.HTTP_200_OK)

    def post(self, request, location_id, *args, **kwargs):
        bdcf = BDCFRings()
        message, http_status = bdcf.add_bogging_movement(request, location_id)
        return Response({'msg': message}, status=http_status)

    def delete(self, request, location_id, *args, **kwargs):
        pk = location_id
        try:
            # Delete the record by its ID (pk)
            bogging_movement = m.BoggedTonnes.objects.get(pk=pk)
            bogging_movement.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

        except m.BoggedTonnes.DoesNotExist:
            return Response({'msg': {'body': 'Record not found', 'type': 'error'}}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, location_id, *args, **kwargs):
        pk = location_id
        try:
            bogging_movement = m.BoggedTonnes.objects.get(pk=pk)

            # Update the 'tonnes' field
            bogging_movement.bogged_tonnes = request.data.get('tonnes')
            bogging_movement.entered_by = request.user
            bogging_movement.save()

            return Response({'msg': {'body': 'Record updated successfully', 'type': 'success'}}, status=status.HTTP_200_OK)

        except m.BoggedTonnes.DoesNotExist:
            return Response({'msg': {'body': 'Record not found', 'type': 'error'}}, status=status.HTTP_404_NOT_FOUND)


class DrillEntryRingsListView(APIView):
    def get(self, request, lvl_od, *args, **kwargs):
        bdcf = BDCFRings()
        drilled_rings = bdcf.get_drilled_rings(lvl_od)
        drilled_list = bdcf.get_rings_of_status_list(lvl_od, 'Drilled')
        designed_list = bdcf.get_rings_of_status_list(lvl_od, 'Designed')
        ring_num_dropdown = {'drilled_rings': drilled_rings,
                             'drilled': drilled_list,
                             'designed': designed_list}

        return Response(ring_num_dropdown, status=status.HTTP_200_OK)


class DrillEntryView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        designed_drives_list = bdcf.get_distict_drives_list('Designed')
        drilled_drives_list = bdcf.get_distict_drives_list('Drilled')
        drives = {'designed_list': designed_drives_list,
                  'drilled_list': drilled_drives_list}
        return Response(drives, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        data = request.data
        location_id = data.get('location_id')
        if not location_id:
            return Response({'msg': {'type': 'error', 'body': 'location_id is required'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ring = m.ProductionRing.objects.get(location_id=location_id)

            drilled_meters = data.get('drilled_mtrs')
            ring.drilled_meters = None if drilled_meters == "" else drilled_meters

            ring.is_redrilled = data.get('redrill', ring.is_redrilled)
            ring.has_lost_rods = data.get('lost_rods', ring.has_lost_rods)
            ring.has_bg_report = data.get('has_bg', ring.has_bg_report)
            ring.is_making_water = data.get(
                'making_water', ring.is_making_water)
            if not data.get('half_drilled'):
                ring.drill_complete_date = data.get(
                    'date', ring.drill_complete_date)
                ring.status = data.get('status', ring.status)

            # Save the updated model instance
            ring.save()

            return Response({'msg': {'body': 'Production ring updated successfully', 'type': 'success'}}, status=status.HTTP_200_OK)

        except m.ProductionRing.DoesNotExist:
            return Response({'msg': {'type': 'error', 'body': 'Production ring not found'}}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            # Handle unexpected errors
            print("error", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChargeEntryView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_blocked()
        half = bdcf.get_half_charged()
        drives = bdcf.get_distict_drives_list('Drilled')
        data = {'blocked_holes': rings, 'incomplete': half,
                'drilled_drives_list': drives}
        return Response(data, status=status.HTTP_200_OK)


class ChargeEntryRingsListView(APIView):
    def get(self, request, lvl_od, *args, **kwargs):
        bdcf = BDCFRings()
        drilled_rings = bdcf.get_drilled_rings(lvl_od)
        drilled_list = bdcf.get_rings_of_status_list(lvl_od, 'Drilled')
        charged_list = bdcf.get_rings_of_status_list(lvl_od, 'Charged')
        ring_num_dropdown = {'drilled_rings': drilled_rings,
                             'drilled': drilled_list,
                             'charged': charged_list}

        return Response(ring_num_dropdown, status=status.HTTP_200_OK)


class FireEntryView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_blocked()
        return Response(rings, status=status.HTTP_200_OK)


class BDCFRings():
    def __init__(self) -> None:
        pass

    def get_rings_status(self, level, status):
        pass

    def get_bogging_rings(self, request):
        current_rings = m.ProductionRing.objects.filter(
            is_active=True, status='Bogging').order_by('level', 'oredrive')
        dropdown_options = []

        # Iterate over the filtered rings
        for ring in current_rings:
            # Determine the concatenated value for multi_fire_group
            if ring.multi_fire_group != '(M)':
                if ring.multi_fire_group:
                    if ring.multi_fire_group == '(MP)':
                        ring_text = f"{ring.level}_{
                            ring.oredrive} R{ring.ring_number_txt}"
                    else:
                        ring_text = f"{ring.level}_{
                            ring.oredrive} {ring.multi_fire_group}"
                else:
                    ring_text = f"{ring.level}_{
                        ring.oredrive} R{ring.ring_number_txt}"

            # Append the formatted result with location_id
                dropdown_options.append({
                    'value': ring_text,
                    'location_id': ring.location_id
                })

        return dropdown_options

    def get_bogging_movements(self, location_id):
        stats = {}
        # Filter BoggedTonnes by ProductionRing location_id
        bogged_entries = m.BoggedTonnes.objects.filter(
            production_ring__location_id=location_id)

        prod_ring = m.ProductionRing.objects.filter(
            is_active=True, location_id=location_id).first()
        if prod_ring:
            stats['in_overdraw_zone'] = prod_ring.in_overdraw_zone
            stats['fired_shift'] = prod_ring.fired_shift
            stats['designed_tonnes'] = prod_ring.designed_tonnes
            stats['draw_percentage'] = prod_ring.draw_percentage
            stats['overdraw_amount'] = prod_ring.overdraw_amount
            stats['draw_deviation'] = prod_ring.draw_deviation
            stats['in_flow'] = prod_ring.in_flow
            stats['comment'] = prod_ring.comment
            stats['flow_tonnes'] = prod_ring.concept_ring.pgca_modelled_tonnes

        total_tonnes = sum(entry.bogged_tonnes for entry in bogged_entries)
        stats['bogged_tonnes'] = total_tonnes

        # Serialize the data as needed
        data = [
            {
                "id": entry.id,
                "tonnes": entry.bogged_tonnes,
                "date": Shkey.format_shkey_day_first(entry.shkey),
                "timestamp": entry.datetime_stamp,
                "contributor": {
                    "full_name": entry.entered_by.get_full_name() if entry.entered_by else "Anonymous User",
                    "avatar": entry.entered_by.avatar if entry.entered_by.avatar else "default.svg",
                    "bg_colour": entry.entered_by.bg_colour if entry.entered_by.bg_colour else "#f5f5f5"
                } if entry.entered_by else None,
            }
            for entry in bogged_entries
        ]

        return {'data': data, 'stats': stats}

    def add_bogging_movement(self, request, location_id):
        form_data = request.data

        mydate = form_data.get('date')
        shift = form_data.get('shift')
        # location_id = form_data.get('location_id')
        tonnes = form_data.get('tonnes')

        # Validate if all required fields are present
        if not all([mydate, shift, location_id, tonnes]):
            return {'type': 'error', 'body': 'Missing data in the request'}, status.HTTP_400_BAD_REQUEST

        try:
            # Assume ProductionRing and Shkey logic here
            production_ring = m.ProductionRing.objects.get(
                location_id=location_id)
            shkey = Shkey.generate_shkey(mydate, shift)

            # Create the BoggedTonnes entry
            m.BoggedTonnes.objects.create(
                production_ring=production_ring,
                bogged_tonnes=tonnes,
                shkey=shkey,
                entered_by=request.user  # Assuming user is authenticated
            )
            return {'type': 'success', 'body': 'Bogging movement added successfully'}, status.HTTP_201_CREATED

        except ObjectDoesNotExist:
            return {'type': 'error', 'body': 'ProductionRing not found.'}, status.HTTP_404_NOT_FOUND

        except Exception as e:
            print(e)
            return {'type': 'error', 'body': 'An error occurred', 'detail': {str(e)}}, status.HTTP_500_INTERNAL_SERVER_ERROR

    def get_distict_drives_list(self, status):
        drives = m.ProductionRing.objects.filter(
            is_active=True,
            status=status
        ).annotate(
            level_oredrive=Concat(
                Cast(F('level'), CharField()), Value('_'), F('oredrive'))
        ).values('level_oredrive').distinct().order_by('level_oredrive')

        return list(drives)

    def get_rings_of_status_list(self, lvl_od, status):
        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status=status
        ).order_by('ring_number_txt').values('ring_number_txt', 'location_id')

        return list(rings)

    def get_drilled_rings(self, lvl_od):
        drilled_rings = []

        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        designed_rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status='Drilled'
        ).order_by('ring_number_txt')

        for ring in designed_rings:

            ring_details = {'location_id': ring.location_id,
                            'drill_complete_date': ring.drill_complete_date,
                            'ring_number_txt': ring.ring_number_txt,
                            'is_making_water': ring.is_making_water,
                            'is_redrilled': ring.is_redrilled,
                            'has_bg_report': ring.has_bg_report,
                            'has_blocked_holes': ring.has_blocked_holes,
                            'has_lost_rods': ring.has_lost_rods
                            }
            drilled_rings.append(ring_details)

        return drilled_rings

    def get_charged_rings(self, lvl_od):
        charged_rings = []

        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        charged_rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status='Charged'
        ).order_by('ring_number_txt')

        for ring in charged_rings:

            ring_details = {'location_id': ring.location_id,
                            'charge_date': ring.charge_date,
                            'ring_number_txt': ring.ring_number_txt,
                            'detonator': ring.detonator_actual
                            }
            charged_rings.append(ring_details)

        return charged_rings

    def get_blocked(self):
        rings = m.ProductionRing.objects.filter(
            is_active=True,
            has_blocked_holes=True
        )

        rings = []
        for r in rings:
            ring = {}
            ring['location_id'] = r.location_id
            ring['level'] = r.level
            ring['oredrive'] = r.oredrive
            ring['ring_number_txt'] = r.ring_number_txt
            ring['has_blocked_holes'] = r.has_blocked_holes

            rings.append(ring)

        return rings

    def get_half_charged(self):
        rings = []
        ring_states = m.RingStateChange.objects.filter(
            is_active=True, state__state='Charge Incomplete')
        for r in ring_states:
            ring = {}
            ring['location_id'] = r.prod_ring.location_id
            ring['level'] = r.prod_ring.level
            ring['oredrive'] = r.prod_ring.oredrive
            ring['ring_number_txt'] = r.prod_ring.ring_number_txt
            ring['has_blocked_holes'] = r.prod_ring.has_blocked_holes
            ring['timestamp'] = r.timestamp
            ring['user_email'] = r.user.email
            ring['state'] = r.state
            ring['comment'] = r.comment
            ring['operation_complete'] = r.operation_complete
            ring['holes_completed'] = r.holes_completed

            rings.append(ring)
        return rings
