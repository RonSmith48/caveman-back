from rest_framework import generics, status
from rest_framework.response import Response
from django.db.models import Sum
import prod_actual.models as m
import prod_actual.api.serializers as s
from common.functions.shkey import Shkey


class OverdrawRingView(generics.ListCreateAPIView):
    queryset = m.ProductionRing.objects.filter(
        is_active=True,
        status='Bogging',
        in_overdraw_zone=True
    ).order_by('level', 'oredrive', 'ring_number_txt')

    serializer_class = s.OverdrawRingSerializer

    def create(self, request, *args, **kwargs):
        ring_id = request.data.get('ring_id')
        quantity = request.data.get('quantity')
        reason = request.data.get('reason')
        status_value = request.data.get('status')

        if ring_id is None or quantity is None:
            return Response({'msg': {'body': 'ring_id and quantity required', 'type': 'error'}}, status=400)

        ring = m.ProductionRing.objects.get(location_id=ring_id)

        m.DrawChange.objects.create(
            ring=ring,
            quantity=quantity,
            reason=reason,
            user=request.user,
            type='overdraw',
        )

        if status_value == 'rejected':
            waste_state = m.RingState.objects.get(
                pri_state='Bogging', sec_state='Waste')

            if not m.RingStateChange.objects.filter(is_active=True, prod_ring=ring, state=waste_state).exists():
                m.RingStateChange.objects.create(
                    prod_ring=ring,
                    state=waste_state,
                    user=request.user,
                    shkey=Shkey.today_shkey(),
                    comment=reason or '',
                )

        else:
            # Only for approved (ore) cases, create a comment
            comment_lines = [f"Overdraw: {quantity}t"]
            if reason:
                comment_lines.append(reason)

            m.RingComments.objects.create(
                ring_id=ring,
                is_active=True,
                department='Geology',
                user=request.user,
                comment="\n".join(comment_lines),
                show_to_operator=["level_status_report", "ring_history"],
            )

        ring.overdraw_amount += int(quantity)
        ring.save()
        if int(quantity) > 0:
            body = 'Overdraw recorded'
        else:
            body = 'Ring declared waste'

        return Response({'msg': {'body': body, 'type': 'success'}}, status=status.HTTP_201_CREATED)
