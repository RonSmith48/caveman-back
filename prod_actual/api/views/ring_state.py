from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Exists, OuterRef

from common.functions.constants import MANDATORY_RING_STATES

import prod_actual.models as m


class RingStateListView(APIView):
    """
    API endpoint to retrieve all RingState entries along with a deletion flag.
    """

    def get(self, request, *args, **kwargs):
        cas = ConditionsAndStates()
        results = cas.get_ring_states()

        return Response(results, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        cas = ConditionsAndStates()
        reply = cas.add_condition(request)
        return Response(reply, status=status.HTTP_200_OK)


class RingStateDeleteView(APIView):
    def post(self, request, *args, **kwargs):
        cas = ConditionsAndStates()
        reply = cas.delete_condition(request)
        return Response(reply, status=status.HTTP_200_OK)


class ConditionsAndStates():
    def __init__(self):
        pass

    def ensure_mandatory_ring_states(self):
        """
        Ensures that all mandatory `RingState` combinations exist in the database.
        Missing combinations will be created.
        """

        for state in MANDATORY_RING_STATES:
            # Use get_or_create to check if the combination exists, and create if missing
            m.RingState.objects.get_or_create(
                pri_state=state["pri_state"],
                # Use None if sec_state is not provided
                sec_state=state.get("sec_state")
            )

    def get_ring_states(self):
        """
        Retrieves all RingState conditions and annotates whether they are referenced
        in RingStateChange and whether they can be deleted.
        """
        ring_states = m.RingState.objects.values(
            "id", "pri_state", "sec_state")

        results = []
        for state in ring_states:
            pri_state = state["pri_state"]
            sec_state = state["sec_state"]

            # Check if the state is mandatory
            is_mandatory = {"pri_state": pri_state,
                            "sec_state": sec_state} in MANDATORY_RING_STATES

            # Check if the state is referenced using the helper method
            is_referenced = self.is_condition_referenced(pri_state, sec_state)

            # Determine if the state can be deleted
            can_be_deleted = not is_mandatory and not is_referenced

            results.append({
                "id": state["id"],
                "pri_state": pri_state,
                "sec_state": sec_state,
                "can_delete": can_be_deleted
            })

        return results

    def add_condition(self, response):
        """
        Adds a new RingState condition, ensuring no duplicates exist.

        Expected Data Format:
        {'pri_state': 'Bogging', 'sec_state': 'Hung Up'}
        """
        data = response.data

        # Validate input
        pri_state = data.get("pri_state")
        sec_state = data.get("sec_state")

        if not pri_state:
            return {"msg": {"body": "Primary state is required.", "type": "error"}}

        # Check if the condition already exists
        if m.RingState.objects.filter(pri_state=pri_state, sec_state=sec_state).exists():
            return {"msg": {"body": "This condition already exists.", "type": "error"}}

        try:
            # Create and save the new record
            m.RingState.objects.create(
                pri_state=pri_state, sec_state=sec_state)
            return {"msg": {"body": "New condition added successfully.", "type": "success"}}
        except IntegrityError:
            return {"msg": {"body": "Database integrity error occurred.", "type": "error"}}
        except ValidationError as e:
            return {"msg": {"body": str(e), "type": "error"}}
        except Exception as e:
            return {"msg": {"body": f"An unexpected error occurred: {str(e)}", "type": "error"}}

    def is_condition_referenced(self, pri_state, sec_state):
        """
        Checks if a RingState condition is referenced in the RingStateChange table.
        Returns True if the condition is in use.
        """
        return m.RingStateChange.objects.filter(
            state__pri_state=pri_state, state__sec_state=sec_state
        ).exists()

    def delete_condition(self, request):
        """
        Deletes a RingState condition.
        Ensures that mandatory conditions and conditions currently in use cannot be deleted.

        Expected request format:
        {'pri_state': 'Bogging', 'sec_state': 'Hung Up'}
        """
        data = request.data
        pri_state = data.get("pri_state")
        sec_state = data.get("sec_state")

        if not pri_state:
            return {"msg": {"body": "Primary state is required.", "type": "error"}}

        try:
            # Check if the condition exists
            condition = m.RingState.objects.filter(
                pri_state=pri_state, sec_state=sec_state).first()
            if not condition:
                return {"msg": {"body": "Condition not found.", "type": "error"}}

            # Check if condition is mandatory
            if {"pri_state": pri_state, "sec_state": sec_state} in MANDATORY_RING_STATES:
                return {"msg": {"body": "Cannot delete a mandatory condition.", "type": "error"}}

            # Check if condition is referenced (in use)
            if self.is_condition_referenced(pri_state, sec_state):
                return {"msg": {"body": "Cannot delete a condition that is currently in use.", "type": "error"}}

            # Delete the condition
            condition.delete()
            return {"msg": {"body": "Condition deleted successfully.", "type": "success"}}

        except ValidationError as e:
            return {"msg": {"body": str(e), "type": "error"}}
        except Exception as e:
            return {"msg": {"body": f"An unexpected error occurred: {str(e)}", "type": "error"}}
