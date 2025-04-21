from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from prod_actual.models import ProductionRing, RingStateChange, RingComments
from prod_actual.api.serializers import RingStateChangeSerializer
from operator import itemgetter
from collections import defaultdict
from common.functions.shkey import Shkey
from prod_actual.api.views.ring_state import ConditionsAndStates


class LocationHistoryView(APIView):
    def get(self, request, location_id):
        ring = get_object_or_404(ProductionRing, location_id=location_id)

        # 1. State Changes (use SHKEY as-is)
        cas = ConditionsAndStates()
        cas.ensure_mandatory_ring_states()
        state_changes = RingStateChange.objects.filter(
            is_active=True,
            prod_ring=ring,
            shkey__isnull=False
        ).order_by('shkey')

        state_data = defaultdict(list)
        for sc in state_changes:
            key = sc.shkey
            state_data[key].append({
                "source": "state",
                "shift": Shkey.format_shkey_day_first(key),
                "state": str(sc.state.pri_state),
                "condition": str(sc.state.sec_state),
                "comment": sc.comment,
                "user": sc.user.get_full_name() if sc.user else ""
            })

        # 2. Comments (convert datetime to SHKEY)
        comments = RingComments.objects.filter(
            is_active=True,
            ring_id=ring
        ).order_by('datetime')

        comment_data = defaultdict(list)
        for comment in comments:
            comment_shkey = Shkey.datetime_to_shkey(comment.datetime)
            comment_data[comment_shkey].append({
                "source": "comments",
                "shift": Shkey.format_shkey_day_first(comment_shkey),
                "user": comment.user.get_full_name() if comment.user else "",
                "comment": comment.comment,
                "department": comment.department,
                "show_to": comment.show_to_operator
            })

        # 3. Merge and sort (comments first, then states for each SHKEY)
        merged = []
        all_shkeys = sorted(set(state_data) | set(comment_data))
        for shkey in all_shkeys:
            merged.extend(comment_data.get(shkey, []))
            merged.extend(state_data.get(shkey, []))

        # 4. Return
        return Response({
            "prod_dev_code": ring.prod_dev_code,
            "timeline": merged
        }, status=status.HTTP_200_OK)
