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
from common.functions.ring_state import ensure_mandatory_ring_states

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


class ConditionsListView(APIView):
    def get(self, request, stat, *args, **kwargs):
        bdcf = BDCFRings()
        state_list = bdcf.get_state_list(stat)

        return Response(state_list, status=status.HTTP_200_OK)


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

            if not data.get('half_drilled'):
                ring.drill_complete_shift = data.get(
                    'date', ring.drill_complete_shift)
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
        drives = bdcf.get_distict_drives_list('Drilled')
        data = {'drilled_drives_list': drives}
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        ensure_mandatory_ring_states()
        bdcf = BDCFRings()
        sk = Shkey()
        data = request.data
        print('data', data)  # =========
        location_id = data.get('location_id')
        if not location_id:
            return Response({'msg': {'type': 'error', 'body': 'location_id is required'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ring = m.ProductionRing.objects.get(location_id=location_id)
            d = data.get('date')
            shift = data.get('shift')

            shkey = data.get('shkey')  # From update
            if not shkey:  # New entry
                shkey = sk.generate_shkey(d, shift)

            ring.charge_shift = shkey
            ring.status = data.get('status', ring.status)
            ring.detonator_actual = data.get(
                'explosive', ring.detonator_actual)

            conditions = data.get('conditions', [])

            # Save the updated model instance
            ring.save()

            # status of 'Drilled' means un-charge
            # status of 'Charged' means charge

            creation_list = bdcf.make_deselected_conditions_inactive(request)
            bdcf.create_ring_conditions(request, creation_list)

            return Response({'msg': {'body': 'Production ring updated successfully', 'type': 'success'}}, status=status.HTTP_200_OK)

        except m.ProductionRing.DoesNotExist:
            return Response({'msg': {'type': 'error', 'body': 'Production ring not found'}}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            # Handle unexpected errors
            print("error", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChargeEntryRingsListView(APIView):
    def get(self, request, lvl_od, *args, **kwargs):
        bdcf = BDCFRings()
        charged_rings = bdcf.get_charged_rings(lvl_od)
        drilled_list = bdcf.get_rings_of_status_list(lvl_od, 'Drilled')
        charged_list = bdcf.get_rings_of_status_list(lvl_od, 'Charged')
        ring_num_dropdown = {'charged_rings': charged_rings,
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

            conditions = self.get_current_conditions(ring, 'Drilled')

            ring_details = {'location_id': ring.location_id,
                            'drill_complete_shift': ring.drill_complete_shift,
                            'ring_number_txt': ring.ring_number_txt,
                            'conditions': conditions
                            }
            drilled_rings.append(ring_details)

        return drilled_rings

    def get_charged_rings(self, lvl_od):
        charged = []

        level, oredrive = lvl_od.split('_', 1)
        level = int(level)
        charged_rings = m.ProductionRing.objects.filter(
            is_active=True,
            level=level,
            oredrive=oredrive,
            status='Charged'
        ).order_by('ring_number_txt')

        for ring in charged_rings:
            conditions = self.get_ring_changes(ring, 'Charged')

            ring_details = {'location_id': ring.location_id,
                            'charge_shift': ring.charge_shift,
                            'ring_number_txt': ring.ring_number_txt,
                            'detonator': ring.detonator_actual,
                            'conditions': conditions
                            }
            charged.append(ring_details)

        return charged

    def get_ring_changes(self, ring, pri_state):
        changes = m.RingStateChange.objects.filter(
            is_active=True, prod_ring=ring, state__pri_state=pri_state)
        conditions = []
        for change in changes:
            c = {'state': change.state.sec_state,
                 'shkey': change.shkey,
                 'comment': change.comment,
                 'mtrs_drilled': change.mtrs_drilled,
                 'created_at': change.created_at,
                 'holes_completed': change.holes_completed,  # int
                 'user': {'name': change.user.get_full_name(),
                          'avatar': change.user.avatar,
                          'email': change.user.email}}
            conditions.append(c)
        return conditions

    def get_blocked(self):
        pass

    def get_half_charged(self):
        pass

    def get_state_list(self, status):
        # Query the database for RingState objects with the given pri_state
        # Order them alphabetically by sec_state and exclude None values
        sec_states = (
            m.RingState.objects.filter(pri_state=status)
            .exclude(sec_state__isnull=True)
            .order_by('sec_state')
            .values_list('sec_state', flat=True)
        )

        return list(sec_states)

    def get_current_conditions(self, ring, status):
        '''
        Returns a list of current conditions for a ring in JSON format.
        [{'attribute': value}, {'attribute': value}]
        '''
        # Retrieve all active RingStateChange entries for the given ring and status
        condition_results = m.RingStateChange.objects.filter(
            is_active=True,
            prod_ring=ring,
            state__pri_state=status
        )

        # Build the JSON response
        conditions = [
            {
                # Secondary state (condition)
                'attribute': state.state.sec_state,
                'shkey': state.shkey,  # Shift key
                'comment': state.comment,
                'operation_complete': state.operation_complete,
                'mtrs_drilled': state.mtrs_drilled,
                'holes_completed': state.holes_completed,
                'updated_at': state.updated_at.isoformat(),  # Include timestamp for clarity
                'user': {
                    'name': state.user.username if state.user else None,
                    'avatar': state.user.avatar if state.user and hasattr(state.user, 'avatar') else None
                }
            }
            for state in condition_results
        ]

        return conditions

    def make_deselected_conditions_inactive(self, request):
        '''
        Makes conditions that have been deselected, inactive
        Removes conditions from the list that remain selected
        Returns a list of conditions that need to be created
        '''
        # Extract required data from the request
        location_id = request.data.get('location_id')
        selected_conditions = request.data.get('conditions', [])
        status = request.data.get('status')
        user = request.user if request.user.is_authenticated else None

        # Retrieve current active states for the specified ring
        current_states = m.RingStateChange.objects.filter(
            is_active=True,
            prod_ring__location_id=location_id
        )

        # Track the conditions that remain to be created
        conditions_to_create = selected_conditions.copy()

        for state in current_states:
            # Extract pri_state and sec_state from the current active state
            pri_state = state.state.pri_state
            sec_state = state.state.sec_state

            # Check if this condition is still selected
            if sec_state in selected_conditions and pri_state == status:
                # If the condition remains selected, remove it from conditions_to_create
                conditions_to_create.remove(sec_state)
            else:
                # If the condition has been deselected, deactivate the current state
                state.is_active = False
                state.deactivated_by = user
                state.save()

        return conditions_to_create

    def create_ring_conditions(self, request, conditions):
        '''
        Create RingStateChange records for a list of conditions.
        Input: request and a list of conditions to be created.
        For empty conditions list, pri_state = status, sec_state = None.
        '''
        # Extract required data from the request
        location_id = request.data.get('location_id')
        status = request.data.get('status')
        user = request.user if request.user.is_authenticated else None
        shkey = request.data.get('shkey')  # More generic term for charge_shift
        comment = request.data.get('comment')
        operation_complete = request.data.get('operation_complete', True)
        mtrs_drilled = request.data.get('mtrs_drilled', 0)
        holes_completed = request.data.get('holes_completed')

        # Get the associated ProductionRing
        try:
            prod_ring = m.ProductionRing.objects.get(location_id=location_id)
        except m.ProductionRing.DoesNotExist:
            return Response(
                {'msg': {'type': 'error', 'body': 'Production ring not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Handle default state creation for empty conditions
        if not conditions:
            # Find the default RingState (sec_state=None)
            ring_state = m.RingState.objects.filter(
                pri_state=status, sec_state=None).first()
            if not ring_state:
                return Response(
                    {'msg': {'type': 'error', 'body': "Default RingState not found"}},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the default RingStateChange
            m.RingStateChange.objects.create(
                prod_ring=prod_ring,
                state=ring_state,
                shkey=shkey,
                user=user,
                comment=comment,
                operation_complete=operation_complete,
                mtrs_drilled=mtrs_drilled,
                holes_completed=holes_completed,
                is_active=True  # Mark as active
            )
            return

        # Iterate through conditions and create RingStateChange entries
        for condition in conditions:
            # Find the corresponding RingState
            ring_state = m.RingState.objects.filter(
                pri_state=status, sec_state=condition).first()
            if not ring_state:
                return Response(
                    {'msg': {'type': 'error', 'body': f"RingState with pri_state '{
                        status}' and sec_state '{condition}' not found"}},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create a new RingStateChange entry
            m.RingStateChange.objects.create(
                prod_ring=prod_ring,
                state=ring_state,
                shkey=shkey,
                user=user,
                comment=comment,
                operation_complete=operation_complete,
                mtrs_drilled=mtrs_drilled,
                holes_completed=holes_completed,
                is_active=True  # Mark as active
            )
