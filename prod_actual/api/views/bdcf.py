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


class DesignedDrivesView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_designed_drives(request)
        return Response(rings, status=status.HTTP_200_OK)


class DesignedRingsListView(APIView):
    def get(self, request, lvl_od, *args, **kwargs):
        bdcf = BDCFRings()
        drilled_list = bdcf.get_designed_rings_list(request, lvl_od)
        return Response(drilled_list, status=status.HTTP_200_OK)


class DrilledRingsListView(APIView):
    def get(self, request, lvl_od, *args, **kwargs):
        bdcf = BDCFRings()
        drilled_list = bdcf.get_drilled_rings_list(request, lvl_od)
        return Response(drilled_list, status=status.HTTP_200_OK)


class DrilledRingsView(APIView):
    def get(self, request, lvl_od, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_drilled_rings(request, lvl_od)
        return Response(rings, status=status.HTTP_200_OK)


class ChargedRingsView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.get_charged_rings(request)
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

    def get_designed_drives(self, request):
        designed_rings = m.ProductionRing.objects.filter(
            is_active=True,
            status='Designed'
        ).annotate(
            level_oredrive=Concat(
                Cast(F('level'), CharField()), Value('_'), F('oredrive'))
        ).values('level_oredrive').distinct().order_by('level_oredrive')

        distinct_list = list(designed_rings)
        return distinct_list

    def get_designed_rings_list(self, request, lvl_od):
        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        designed_rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status='Designed'
        ).order_by('ring_number_txt').values('ring_number_txt', 'location_id')

        return list(designed_rings)

    def get_drilled_rings_list(self, request, lvl_od):
        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        designed_rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status='Drilled'
        ).order_by('ring_number_txt').values('ring_number_txt', 'location_id')

        return list(designed_rings)

    def get_drilled_rings(self, request, lvl_od):
        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        designed_rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status='Drilled'
        ).order_by('ring_number_txt').values('ring_number_txt', 'location_id')

        return list(designed_rings)

    def get_charged_rings(self, request):
        pass
