from django.shortcuts import get_object_or_404, render
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Sum, F, Value, CharField
from django.db.models.functions import Concat, Cast

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.functions.common_methods import CommonMethods
from common.functions.shkey import Shkey
from prod_actual.api.views.ring_state import ConditionsAndStates
from prod_actual.api.views.prod_orphans import ProdOrphans
from common.functions.status import Status

from datetime import timedelta, date

import prod_actual.models as m
import prod_actual.api.serializers as s
import prod_concept.models as cm
import prod_concept.api.serializers as cs
import users.api.serializers as us
import json
import math
import random


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
        bdcf = BDCFRings()
        reply = bdcf.drill_ring(request)
        return Response(reply, status=status.HTTP_200_OK)


class ChargeEntryView(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        drives = bdcf.get_distict_drives_list('Drilled')
        data = {'drilled_drives_list': drives}
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        cas = ConditionsAndStates()
        cas.ensure_mandatory_ring_states()
        bdcf = BDCFRings()
        return bdcf.charge_drilled_ring(request)

    def patch(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        return bdcf.update_charged_ring(request)


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
        rings = bdcf.get_levels_list_with_status('Charged')
        return Response(rings, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        rings = bdcf.fire_ring(request)
        return Response(rings, status=status.HTTP_200_OK)


class FiredRings(APIView):
    def get(self, request, lvl, *args, **kwargs):
        bdcf = BDCFRings()
        method_args = {'create_from': 'Charged', 'level': lvl}
        charged = bdcf.get_rings_of_status_on_level(method_args)
        charged_rings = bdcf.add_orphan_status(charged)
        method_args['create_from'] = 'Bogging'
        fired_rings = bdcf.get_rings_of_status_on_level(method_args)
        fired_detail = bdcf.get_fired_ring_detail(fired_rings)

        return Response({'charged_rings': charged_rings, 'fired_rings': fired_detail, 'msg': bdcf.msg}, status=status.HTTP_200_OK)
    
class UnFireRingView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        bdcf = BDCFRings()
        reply = bdcf.unfire_ring(request, location_id)
        return Response(reply, status=status.HTTP_200_OK)


class GroupFromStatusView(APIView):
    def get(self, response, stat, *args, **kwargs):
        bdcf = BDCFRings()
        levels_list = bdcf.get_levels_list_with_status(stat)
        return Response(levels_list, status=status.HTTP_200_OK)


class GroupRingSelection(APIView):
    def post(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        lvl_rings = bdcf.get_rings_of_status_on_level(request.data)
        return Response(lvl_rings, status=status.HTTP_200_OK)


class GroupAggregate(APIView):
    def post(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        details = bdcf.aggregate_rings(request)
        return Response(details, status=status.HTTP_200_OK)


class GroupCustomRings(APIView):
    def post(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        details = bdcf.custom_rings(request)
        return Response(details, status=status.HTTP_200_OK)


class GroupsExisting(APIView):
    def get(self, request, *args, **kwargs):
        bdcf = BDCFRings()
        group_data = bdcf.get_existing_groups(request)
        return Response(group_data, status=status.HTTP_200_OK)


class GroupRemove(APIView):
    def get(self, request, group, *args, **kwargs):
        bdcf = BDCFRings()
        reply = bdcf.delete_group(request, group)
        return Response(reply, status=status.HTTP_200_OK)


class LocationDetailView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        bdcf = BDCFRings()
        details = bdcf.get_prod_location_details(location_id)
        return Response(details, status=status.HTTP_200_OK)


class StatusRollbackView(APIView):
    def get(self, request, location_id, *args, **kwargs):
        bdcf = BDCFRings()
        details = bdcf.do_status_rollback(request, location_id)
        return Response(details, status=status.HTTP_200_OK)


class BDCFRings():
    def __init__(self) -> None:
        self.error_msg = None
        self.msg = None

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
            summed = (prod_ring.designed_tonnes * prod_ring.draw_percentage) + \
                prod_ring.draw_deviation + prod_ring.overdraw_amount
            if prod_ring.concept_ring:
                stats['flow_tonnes'] = prod_ring.concept_ring.pgca_modelled_tonnes
            else:
                stats['flow_tonnes'] = 0
                self.msg = {
                    'body': f'{prod_ring.alias} is an orphaned ring', 'type': 'warning'}

        total_tonnes = sum(entry.bogged_tonnes for entry in bogged_entries)
        stats['bogged_tonnes'] = total_tonnes
        stats['remaining'] = round((summed - total_tonnes), 0)

        self.update_prodring_bogged_tonnes(location_id, total_tonnes)

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

    def update_prodring_bogged_tonnes(self, location_id, bogged_tonnes):
        try:
            production_ring = m.ProductionRing.objects.get(
                location_id=location_id)
            production_ring.bogged_tonnes = bogged_tonnes
            production_ring.save(update_fields=["bogged_tonnes"])
            return True  # Return True to indicate success
        except m.ProductionRing.DoesNotExist:
            self.error_msg = "Could not update bogged tonnes for prod ring"
            return False  # Return False if the production ring is not found

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

    def charge_drilled_ring(self, request):
        sk = Shkey()

        data = request.data
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

            self.create_ring_conditions(request, conditions)

            return Response({'msg': {'body': 'Production ring updated successfully', 'type': 'success'}}, status=status.HTTP_200_OK)

        except m.ProductionRing.DoesNotExist:
            return Response({'msg': {'type': 'error', 'body': 'Production ring not found'}}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            # Handle unexpected errors
            print("error", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update_charged_ring(self, request):
        data = request.data
        location_id = data.get('location_id')
        # Ensure conditions is a set
        conditions = set(data.get('conditions', []))
        user = request.user
        shkey = Shkey.today_shkey()
        comment = data.get('comment', '')

        if not location_id:
            return Response({'msg': {'body': 'Location ID is required', 'type': 'error'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Retrieve production ring
                ring = m.ProductionRing.objects.get(location_id=location_id)

                # Fetch existing active state changes
                state_change_qs = m.RingStateChange.objects.filter(
                    prod_ring=ring, is_active=True, state__pri_state=ring.status
                )

                # Deactivate states not in conditions
                for sc in state_change_qs:
                    if sc.state.id in conditions:
                        # Remove from set if already active
                        conditions.remove(sc.state.id)
                    else:
                        sc.is_active = False
                        sc.deactivated_by = user
                        sc.save()

                # Add new conditions
                for c in conditions:
                    m.RingStateChange.objects.create(
                        prod_ring=ring,
                        shkey=shkey,
                        user=user,
                        state_id=c,  # Use state_id instead of empty string
                        comment=comment
                    )

            return Response({'msg': {'body': 'Production ring updated successfully', 'type': 'success'}}, status=status.HTTP_200_OK)

        except m.ProductionRing.DoesNotExist:
            return Response({'msg': {'body': 'Production ring not found', 'type': 'error'}}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'msg': {'body': f'Error updating production ring: {str(e)}', 'type': 'error'}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    def get_rings_of_status_on_level(self, data):
        status = data.get('create_from')
        level = data.get('level')

        rings_qs = (
            m.ProductionRing.objects
            .filter(is_active=True, status=status, level=level)
            .order_by('alias')  # Order by alias
            # Return only required fields
            .values('alias', 'location_id', 'fired_shift', 'oredrive')
        )

        return list(rings_qs)

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
        states = (
            m.RingState.objects.filter(pri_state=status)
            .exclude(sec_state__isnull=True)
            .order_by('sec_state')
            .values('id', 'sec_state')
        )
        return list(states)

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
                'state': state.state.sec_state,
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

    def create_ring_conditions(self, request, conditions):
        '''
        Create RingStateChange records for a list of conditions.
        Input: request and a list of conditions to be created.
        For empty conditions list, pri_state = status, sec_state = None.
        '''
        sk = Shkey()

        data = request.data
        d = data.get('date')
        shift = data.get('shift')
        shkey = data.get('shkey')
        if not shkey:  # New entry
            shkey = sk.generate_shkey(d, shift)

        # Extract required data from the request
        location_id = data.get('location_id')
        status = data.get('status')
        user = request.user if request.user.is_authenticated else None
        comment = data.get('comment')
        operation_complete = data.get('operation_complete', True)
        mtrs_drilled = data.get('mtrs_drilled', 0)
        holes_completed = data.get('holes_completed')

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

    def get_prod_location_details(self, location_id):
        try:
            prod_ring = m.ProductionRing.objects.get(location_id=location_id)
        except m.ProductionRing.DoesNotExist:
            return Response(
                {'msg': {'type': 'error', 'body': 'Production ring not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Serialize the ProductionRing with excluded unserializable fields.
        prod_ring_serializer = s.ProdRingSerializer(prod_ring)
        prod_ring_data = prod_ring_serializer.data

        # Similarly serialize the related ConceptRing.
        concept_ring_serializer = cs.ConceptRingSerializer(
            prod_ring.concept_ring)
        concept_ring_data = concept_ring_serializer.data

        # Serialize the RingStateChange queryset.
        changes_qs = m.RingStateChange.objects.filter(prod_ring=prod_ring)
        changes_data = []
        for change in changes_qs:
            c_serializer = s.RingStateChangeSerializer(change)
            c_data = c_serializer.data
            c_data['deactivated'] = (
                us.UserSerializer(
                    change.deactivated_by).data if change.deactivated_by else None
            )
            # Serialize the 'user' field if it exists
            c_data['activated'] = (
                us.UserSerializer(change.user).data if change.user else None
            )
            c_data['pri_state'] = change.state.pri_state
            c_data['sec_state'] = change.state.sec_state

            changes_data.append(c_data)

        return {
            "prod_ring": prod_ring_data,
            "concept_ring": concept_ring_data,
            "changes": changes_data,
        }

    def do_status_rollback(self, request, location_id):
        ring = get_object_or_404(m.ProductionRing, location_id=location_id)
        current_status = ring.status
        s = Status(current_status)

        prev_status = s.prev_status()
        if prev_status is None:
            return {'msg': {'type': 'error', 'body': 'Cannot roll back status'}}

        with transaction.atomic():
            # Update ring status and clear fields
            ring.status = prev_status
            ring.charge_shift = None
            ring.detonator_actual = None
            ring.save()

            # Bulk update instead of looping
            m.RingStateChange.objects.filter(
                prod_ring=ring, state__pri_state=current_status
            ).update(is_active=False, deactivated_by=request.user)

            # Get new state
            ring_state_obj = m.RingState.objects.filter(
                pri_state=ring.status, sec_state=None
            ).first()

            if not ring_state_obj:
                return {'msg': {'type': 'error', 'body': 'No matching RingState found'}}

            # Create new state change
            m.RingStateChange.objects.create(
                prod_ring=ring,
                state=ring_state_obj,
                user=request.user,
                is_active=True
            )

        return {'msg': {'type': 'success', 'body': 'Happy days'}}

    def get_levels_list_with_status(self, status):
        # using python list/set because using distinct has to be
        # written differently depending on DB used.
        levels = sorted(set(
            m.ProductionRing.objects
            .filter(is_active=True, status=status)
            .values_list('level', flat=True)
        ))
        return levels

    def aggregate_rings(self, request):
        data = request.data
        ring_id_list = data.get('location_ids')
        ring_list = []

        for id in ring_id_list:
            prod_ring = m.ProductionRing.objects.get(location_id=id)
            ring_measures = self.get_ring_measures(prod_ring)
            if self.error_msg:
                return {'msg': {'type': 'error', 'body': self.error_msg}}
            ring_list.append(ring_measures)
        aggregates = self.calculate_aggregated_total(ring_list)
        form_elements = self.group_form_data(ring_list)

        return {'rings': ring_list, 'aggregate': aggregates, 'form_elements': form_elements}

    def group_form_data(self, ring_list):
        if not ring_list:
            # Handle empty input gracefully
            return {'level': None, 'oredrive': []}

        level = ring_list[0]['level']
        oredrive = list({ring['oredrive']
                        for ring in ring_list})  # Convert set to list

        return {'level': level, 'oredrive': oredrive}

    def calculate_aggregated_total(self, ring_list):
        emulsion_omitted = False
        aggregated = {
            'designed_tonnes': 0,
            'volume': 0,
            'designed_emulsion_kg': 0,
            'avg_density': 0,
            'avg_modelled_au': 0,
            'avg_modelled_cu': 0
        }

        total_weight_density = 0
        total_weight_au = 0
        total_weight_cu = 0
        valid_weighted_rings = 0  # Count rings with valid tonnes/volume for averaging

        for ring in ring_list:
            tonnes = ring['designed_tonnes']
            volume = ring['volume']

            if tonnes > 0 and volume > 0:
                # missing volumes have been added in get_ring_measures method
                if ring['in_flow']:
                    # we are expecting a certain volume of material to be bogged
                    # from flow rings
                    aggregated['designed_tonnes'] += (
                        tonnes * ring['draw_percentage'])
                    aggregated['volume'] += ((tonnes *
                                             ring['draw_percentage']) / ring['density'])
                else:
                    aggregated['designed_tonnes'] += tonnes
                    aggregated['volume'] += volume

                valid_weighted_rings += 1

                # Weighted sums for weighted average calculations
                total_weight_density += ring['density'] * tonnes
                total_weight_au += ring['modelled_au'] * tonnes
                total_weight_cu += ring['modelled_cu'] * tonnes

            # Always include `designed_emulsion_kg`, even for single-hole rings with no tonnes/volume
            if not ring['designed_emulsion_kg']:
                emulsion_omitted = True
            elif not emulsion_omitted:
                aggregated['designed_emulsion_kg'] += ring['designed_emulsion_kg']

        # Compute weighted averages only if there are valid rings contributing weight
        if aggregated['designed_tonnes'] > 0:
            aggregated['avg_density'] = round(
                total_weight_density / aggregated['designed_tonnes'], 3)
            aggregated['avg_modelled_au'] = round(
                total_weight_au / aggregated['designed_tonnes'], 3)
            aggregated['avg_modelled_cu'] = round(
                total_weight_cu / aggregated['designed_tonnes'], 3)

        return aggregated

    def get_ring_measures(self, ring):
        """Extracts and calculates various measures for a given ring."""

        # Ensure the ring is not orphaned
        if not ring.concept_ring:
            self.error_msg = "Cannot process orphaned rings"
            return

        measures = {
            'location_id': ring.location_id,
            'level': ring.level,
            'oredrive': ring.oredrive,
            'alias': ring.alias,  # str
            'volume': ring.blastsolids_volume,  # dec
            'designed_emulsion_kg': ring.designed_emulsion_kg,  # int
            'draw_percentage': ring.draw_percentage,  # dec
            'holes': ring.holes,  # int
            'in_flow': ring.in_flow,  # bool
            'x': ring.x,  # dec
            'y': ring.y,  # dec
            'z': ring.z,  # dec
            'density': ring.concept_ring.density,  # dec
            'modelled_au': ring.concept_ring.modelled_au,  # dec
            'modelled_cu': ring.concept_ring.modelled_cu,  # dec
            'status': ring.status,
            'drill_complete_shift': ring.drill_complete_shift,
            'charge_shift': ring.charge_shift,
            'detonator_designed': ring.detonator_designed,
            'detonator_actual': ring.detonator_actual,
            'design_date': ring.design_date,
            'fireby_date': ring.fireby_date
        }

        if ring.in_flow:
            # if multiple rings sharing flow ring, draw percentage must be already divided
            measures['designed_tonnes'] = ring.concept_ring.pgca_modelled_tonnes
        else:
            measures['designed_tonnes'] = ring.designed_tonnes  # dec
        # If the ring has holes but no volume, calculate volume based on density
        if ring.holes and ring.holes > 1 and not ring.blastsolids_volume:
            if ring.concept_ring.density > 0:
                # volume = tonnes / density
                measures['volume'] = round(
                    ring.designed_tonnes / ring.concept_ring.density, 3)
            else:
                self.error_msg = "Ring cannot have a zero density"
                return

        return measures

    def custom_rings(self, request):
        data = request.data
        concept_ring = self.create_private_concept_ring(data)
        if self.error_msg:
            return {'msg': {'type': 'error', 'body': self.error_msg}}
        custom_rings = self.create_custom_rings(data, concept_ring)
        self.create_multifire_record(request, custom_rings)
        self.deactivate_replaced_rings(data)

        return {'msg': {'type': 'success', 'body': 'Nice'}}

    def create_private_concept_ring(self, attributes):
        avg_xyz = self.calc_avg_xyz(attributes['original'])
        level = attributes['original'][0]['level']
        closest_concept = self.find_closest_concept(level, avg_xyz)
        bs_id = self.generate_blastsolids_id(closest_concept)
        ag = attributes['aggregate']

        concept_ring = cm.FlowModelConceptRing(
            description=closest_concept.description,
            prod_dev_code='C',
            # created inactive so no-one assigns other rings to it
            is_active=False,
            comment='group',
            level=level,
            status='Group',
            x=avg_xyz['x'],
            y=avg_xyz['y'],
            z=avg_xyz['z'],
            blastsolids_id=bs_id,
            heading=closest_concept.heading,
            drive=closest_concept.drive,
            loc=closest_concept.loc,
            pgca_modelled_tonnes=ag['designed_tonnes'],
            draw_zone=0,
            density=ag['avg_density'],
            modelled_au=ag['avg_modelled_au'],
            modelled_cu=ag['avg_modelled_cu']
        )

        concept_ring.save()

        return concept_ring

    def generate_blastsolids_id(self, concept_ring):
        hex_number = f"{random.randint(0x1000000, 0xFFFFFFF):07X}"
        return f"{concept_ring.description}_z{hex_number}"

    def calc_avg_xyz(self, input_rings):
        num_rings = len(input_rings)
        if num_rings == 0:
            return {'x': None, 'y': None, 'z': None}

        x = y = z = 0
        for ring in input_rings:
            x += ring['x']
            y += ring['y']
            z += ring['z']

        x1 = round(x / num_rings, 3)
        y1 = round(y / num_rings, 3)
        z1 = round(z / num_rings, 3)

        return {'x': x1, 'y': y1, 'z': z1}

    def find_closest_concept(self, level, xyz):
        all_rings = cm.FlowModelConceptRing.objects.filter(
            is_active=True, level=level).values('location_id', 'x', 'y')

        if not all_rings:
            return None  # No rings found

        # Calculate distance for each ring
        closest_ring = min(
            all_rings,
            key=lambda ring: math.dist(
                (ring['x'], ring['y']), (xyz['x'], xyz['y']))
        )

        # Fetch the actual object from the DB
        return cm.FlowModelConceptRing.objects.get(location_id=closest_ring['location_id'])

    def create_custom_rings(self, data, concept_ring):
        common = self.get_common_attributes(data['original'])
        ring_details = []

        for custom_ring in data['custom']:
            if custom_ring['tonnes']:
                tonnes = custom_ring['tonnes']
                volume = tonnes / data['aggregate']['avg_density']
            else:
                volume = custom_ring['volume']
                tonnes = volume * data['aggregate']['avg_density']

            level = custom_ring['level']
            oredrive = custom_ring['oredrive']
            ring_name = custom_ring['name']
            alias = f"{level}_{oredrive}_{ring_name}"

            ring = m.ProductionRing(
                alias=alias,
                prod_dev_code='P',
                is_active=True,
                comment='custom ring',
                level=level,
                status=common['status'],
                x=concept_ring.x,
                y=concept_ring.y,
                z=concept_ring.z,
                concept_ring=concept_ring,
                oredrive=oredrive,
                ring_number_txt=ring_name,
                drill_complete_shift=common['drill_complete_shift'] or "",
                charge_shift=common['charge_shift'] or "",
                detonator_designed=common['detonator_designed'] or "",
                detonator_actual=common['detonator_actual'] or "",
                design_date=common['design_date'] or "",
                fireby_date=common['fireby_date'] or "",
                blastsolids_volume=volume,
                designed_tonnes=tonnes,
                draw_percentage=custom_ring['draw_percentage']
            )
            ring.save()
            ring_details.append(
                {'alias': alias, 'location_id': ring.location_id})

        return {'concept_ring': concept_ring.location_id, 'ring_details': ring_details}

    def get_common_attributes(self, original):
        common = {
            'drill_complete_shift': None,
            'charge_shift': None,
            'detonator_designed': None,
            'detonator_actual': None,
            'design_date': None,
            'fireby_date': None,
            'status': None
        }

        # Track unique values for fields that need to be consistent
        detonator_designed_values = set()
        detonator_actual_values = set()

        for ring in original:
            common['status'] = ring['status']

            if ring['drill_complete_shift'] and (common['drill_complete_shift'] is None or ring['drill_complete_shift'] > common['drill_complete_shift']):
                common['drill_complete_shift'] = ring['drill_complete_shift']
            if ring['charge_shift'] and (common['charge_shift'] is None or ring['charge_shift'] > common['charge_shift']):
                common['charge_shift'] = ring['charge_shift']

            # Collect unique values for detonator fields
            if ring['detonator_designed']:
                detonator_designed_values.add(ring['detonator_designed'])
            if ring['detonator_actual']:
                detonator_actual_values.add(ring['detonator_actual'])

            # Latest design_date and fireby_date based on valid values
            if ring['design_date'] and (common['design_date'] is None or ring['design_date'] > common['design_date']):
                common['design_date'] = ring['design_date']
            if ring['fireby_date'] and (common['fireby_date'] is None or ring['fireby_date'] > common['fireby_date']):
                common['fireby_date'] = ring['fireby_date']

        # If there is only one unique value for detonator fields, set it; otherwise, leave it as None
        if len(detonator_designed_values) == 1:
            common['detonator_designed'] = detonator_designed_values.pop()
        if len(detonator_actual_values) == 1:
            common['detonator_actual'] = detonator_actual_values.pop()

        return common

    def create_multifire_record(self, request, custom_rings):
        data = request.data
        # Validate original rings exist
        if not data.get('original'):
            raise ValueError("Missing or empty 'original' rings data")

        # Extract necessary fields safely
        aggregate = data.get('aggregate', {})

        original_rings = [
            {'location_id': ring['location_id'], 'alias': ring['alias']}
            for ring in data['original']
        ]

        # Ensure required keys exist in aggregate data
        required_keys = ['volume', 'designed_tonnes',
                         'avg_density', 'avg_modelled_au', 'avg_modelled_cu']
        for key in required_keys:
            if key not in aggregate:
                raise KeyError(f"Missing required aggregate key: {key}")

        if not request.user.is_authenticated:
            raise PermissionError(
                "User must be authenticated to create a record.")

        mfg = m.MultifireGroup(
            name='',
            level=data['original'][0]['level'],
            total_volume=data['aggregate']['volume'],
            total_tonnage=data['aggregate']['designed_tonnes'],
            avg_density=data['aggregate']['avg_density'],
            avg_au=data['aggregate']['avg_modelled_au'],
            avg_cu=data['aggregate']['avg_modelled_cu'],
            pooled_rings={'status': data['original']
                          [0]['status'], 'concept_ring': custom_rings['concept_ring'], 'rings': original_rings},
            group_rings=custom_rings['ring_details'],
            entered_by=request.user
        )
        mfg.save()

    def deactivate_replaced_rings(self, data):
        # Validate data structure
        if not data.get('original'):
            raise ValueError("Missing or empty 'original' rings data")

        # Extract location IDs
        location_ids = [rng['location_id']
                        for rng in data['original'] if 'location_id' in rng]

        if not location_ids:
            raise ValueError("No valid location IDs provided.")

        # Bulk update rings to deactivate in one query
        m.ProductionRing.objects.filter(
            location_id__in=location_ids).update(is_active=False)

    def get_existing_groups(self, request):
        groups = []
        mfg = m.MultifireGroup.objects.filter(is_active=True)
        for g in mfg:

            touched = True
            created_rings_info = self.get_created_rings_status(g.group_rings)
            if g.pooled_rings['status'] == created_rings_info['status'] and not created_rings_info['touched']:
                touched = False
            row = {'id': g.multifire_group_id,
                   'date': g.created_at,
                   'level': g.level,
                   'contributor': {
                       "full_name": g.entered_by.get_full_name() if g.entered_by else "Anonymous User",
                       "avatar": g.entered_by.avatar if g.entered_by.avatar else "default.svg",
                       "bg_colour": g.entered_by.bg_colour if g.entered_by.bg_colour else "#f5f5f5"
                   } if g.entered_by else None,
                   'touched': touched,
                   'pooled_rings': g.pooled_rings,
                   'group_rings': created_rings_info['rings'],
                   'oredrive': created_rings_info['oredrive']}
            groups.append(row)

        return groups

    def get_created_rings_status(self, group_rings):
        oredrive = None
        oredrive_same = True
        status_same = True
        status = None
        rings_list = []

        for r in group_rings:
            ring = m.ProductionRing.objects.get(location_id=r['location_id'])
            ring_status = ring.status
            ring_oredrive = ring.oredrive

            if status and ring_status != status:
                status_same = False
            else:
                status = ring_status

            if oredrive and ring_oredrive != oredrive:
                oredrive_same = False
            else:
                oredrive = ring_oredrive

            ring_info = {'location_id': r['location_id'],
                         'alias': r['alias'],
                         'status': ring_status}
            rings_list.append(ring_info)

        if oredrive_same == False:
            oredrive = 'Multiple'

        return {'touched': not status_same, 'status': status, 'rings': rings_list, 'oredrive': oredrive}

    def delete_group(self, request, group):
        try:
            mf_group = m.MultifireGroup.objects.get(multifire_group_id=group)

            # Reactivate original rings in one query
            pooled_ring_ids = [p['location_id']
                               for p in mf_group.pooled_rings['rings']]
            m.ProductionRing.objects.filter(
                location_id__in=pooled_ring_ids).update(is_active=True)

            # Delete custom rings in one query
            group_ring_ids = [r['location_id'] for r in mf_group.group_rings]
            m.ProductionRing.objects.filter(
                location_id__in=group_ring_ids).delete()

            # Delete private concept ring
            cm.FlowModelConceptRing.objects.filter(
                location_id=mf_group.pooled_rings['concept_ring']).delete()

            # Deactivate multifire group
            mf_group.is_active = False
            mf_group.deactivated_by = request.user
            mf_group.save()

            return True  # Indicate successful deletion

        except m.MultifireGroup.DoesNotExist:
            return False  # Group not found

        except Exception as e:
            # Log the error if you have logging enabled
            print(f"Error deleting group: {e}")
            return False

    def fire_ring(self, request):
        data = request.data
        sk = Shkey()
        date = data['date']
        shift = data['shift']
        location_id = data['location_id']
        oredrive = data['oredrive']

        shkey = sk.generate_shkey(date, shift)
        replacing = []  # Ensure 'replacing' is always a list, even if empty

        try:
            with transaction.atomic():
                cas = ConditionsAndStates()
                cas.ensure_mandatory_ring_states()

                # Get ring(s) being replaced
                completed = m.ProductionRing.objects.filter(
                    is_active=True, status='Bogging', oredrive=oredrive
                )

                # Update the status of the replaced rings and collect their IDs
                for c in completed:
                    replacing.append(c.location_id)
                    c.status = 'Complete'
                    c.bog_complete_shift = shkey
                    c.save()

                # Get the ring to be fired
                firing = m.ProductionRing.objects.select_for_update().get(location_id=location_id)
                firing.status = "Bogging"
                firing.fired_shift = shkey
                firing.save()

                # Get the 'Bogging' state
                bogging_state = m.RingState.objects.get(
                    pri_state='Bogging', sec_state=None)

                # Create a state change entry
                m.RingStateChange.objects.create(
                    prod_ring=firing,
                    shkey=shkey,
                    user=request.user,
                    state=bogging_state,
                    # Will store an empty list if nothing is replaced
                    detail={'replacing': replacing}
                )

            return {'msg': {'body': 'Ring fired successfully', 'type': 'success'}}

        except m.ProductionRing.DoesNotExist:
            return {'msg': {'body': 'Error: Production ring not found', 'type': 'error'}}
        except m.RingState.DoesNotExist:
            return {'msg': {'body': 'Error: Bogging state not found', 'type': 'error'}}
        except Exception as e:
            return {'msg': {'body': f'Unexpected error: {str(e)}', 'type': 'error'}}

    def unfire_ring(self, request, location_id):

        try:
            with transaction.atomic():
                # Find the most recent active RingStateChange entry
                ring_state_change = m.RingStateChange.objects.filter(
                    prod_ring__location_id=location_id,
                    state__pri_state='Bogging',  # Ensure it's a 'Bogging' entry
                    is_active=True
                ).select_for_update().order_by('-created_at').first()

                if not ring_state_change:
                    return {'msg': {'body': 'Error: No active firing record found', 'type': 'error'}}

                # Get the rings that were replaced
                replacing = ring_state_change.detail['replacing'] if ring_state_change.detail else [
                ]

                # Set the deactivation state
                ring_state_change.is_active = False
                ring_state_change.deactivated_by = request.user
                ring_state_change.save()

                # Change status of replaced rings back to "Bogging"
                if replacing:
                    m.ProductionRing.objects.filter(
                        location_id__in=replacing).update(status='Bogging', bog_complete_shift=None)

                # Deactivate the primary fired ring
                fired_ring = ring_state_change.prod_ring
                fired_ring.status = 'Charged'  # Default status before being fired
                fired_ring.fired_shift = None
                fired_ring.save()

                msg = self.do_status_rollback(request, location_id)

            return {'msg': {'body': 'Reversal complete, ring unfired successfully', 'type': 'success'}}

        except m.RingStateChange.DoesNotExist:
            return {'msg': {'body': 'Error: No valid state change found', 'type': 'error'}}
        except Exception as e:
            return {'msg': {'body': f'Unexpected error: {str(e)}', 'type': 'error'}}

    def get_fired_ring_detail(self, fired_rings):
        rings = []
        for fr in fired_rings:
            fr_copy = fr.copy()  # Prevent modifying original data
            location_id = fr_copy['location_id']
            movements = self.get_bogging_movements(location_id)
            fr_copy['remaining'] = movements['stats']['remaining']

            try:
                rsc = m.RingStateChange.objects.filter(
                    is_active=True,
                    prod_ring__location_id=location_id,
                    state__pri_state='Bogging',
                    state__sec_state=None
                ).first()

                if rsc and rsc.user:
                    fr_copy['contributor'] = {
                        "full_name": rsc.user.get_full_name() if rsc.user else "Anonymous User",
                        "avatar": rsc.user.avatar or "default.svg",
                        "bg_colour": rsc.user.bg_colour or "#f5f5f5"
                    }
                else:
                    fr_copy['contributor'] = None

            except (AttributeError, m.RingStateChange.DoesNotExist) as e:
                # Log the error instead of returning False
                self.custom_logger.error(
                    f"Error in get_fired_ring_detail: {e}")
                return []

            rings.append(fr_copy)

        return rings

    def add_orphan_status(self, charged):
        # True or False
        po = ProdOrphans()

        for entry in charged:
            location_id = entry.get("location_id")
            if location_id is not None:
                entry["orphaned"] = po.is_orphan(location_id)

        return charged

    def drill_ring(self, request):
        data = request.data
        location_id = data.get('location_id')
        drilled_date = data.get('date')
        shift = data.get('shift')
        shkey = Shkey.generate_shkey(drilled_date, shift)
        if not location_id:
            return {'msg': {'type': 'error', 'body': 'location_id is required'}}

        try:
            ring = m.ProductionRing.objects.get(location_id=location_id)

            drilled_meters = data.get('drilled_mtrs')
            ring.drilled_meters = None if drilled_meters == "" else drilled_meters

            if not data.get('half_drilled'):
                ring.drill_complete_shift = shkey
                ring.status = data.get('status', ring.status)

            # Save the updated model instance
            ring.save()

            conditions = request.data.get('conditions')
            self.create_ring_conditions(request, conditions)

            return {'msg': {'body': 'Production ring updated successfully', 'type': 'success'}}

        except m.ProductionRing.DoesNotExist:
            return {'msg': {'type': 'error', 'body': 'Production ring not found'}}

        except Exception as e:
            # Handle unexpected errors
            print("error", str(e))
            return {'msg': {'type': 'error', 'body': f'error: {str(e)}'}}
