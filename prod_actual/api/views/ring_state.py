from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Exists, OuterRef
from common.functions.constants import MANDATORY_RING_STATES

import prod_actual.models as m


class RingStateListView(APIView):
    """
    API endpoint to retrieve all RingState entries along with a deletion flag.
    """

    def get(self, request, *args, **kwargs):
        # Annotate whether each RingState is referenced in RingStateChange
        referenced_states = m.RingStateChange.objects.filter(
            state=OuterRef('pk'))

        ring_states = m.RingState.objects.annotate(
            is_referenced=Exists(referenced_states)
        ).values("id", "pri_state", "sec_state", "is_referenced")

        results = []
        for state in ring_states:
            pri_state = state["pri_state"]
            sec_state = state["sec_state"]

            # Check if state is mandatory
            is_mandatory = {"pri_state": pri_state,
                            "sec_state": sec_state} in MANDATORY_RING_STATES

            # Determine if the state can be deleted
            can_be_deleted = not is_mandatory and not state["is_referenced"]

            results.append({
                "id": state["id"],
                "pri_state": pri_state,
                "sec_state": sec_state,
                "can_delete": can_be_deleted
            })

        return Response(results, status=status.HTTP_200_OK)


class ConditionsAndStates():
    def __init__(self):
        pass

    def ensure_mandatory_ring_states():
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
