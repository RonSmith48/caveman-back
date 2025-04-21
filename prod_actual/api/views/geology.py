from rest_framework import generics, status
from rest_framework.response import Response
from django.db.models import Sum
import prod_actual.models as m
import prod_actual.api.serializers as s


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

        if ring_id is None or quantity is None:
            return Response({'detail': 'ring_id and quantity required'}, status=400)

        ring = m.ProductionRing.objects.get(location_id=ring_id)

        draw_change = m.DrawChange.objects.create(
            ring=ring,
            quantity=quantity,
            reason=reason,
            user=request.user,
            type='overdraw',
        )

        comment_lines = [f"Overdraw: {quantity}t"]
        if reason:
            comment_lines.append(reason)

        geo_comment = m.RingComments.objects.create(
            ring_id=ring,
            is_active=True,
            department='Geology',
            user=request.user,
            comment="\n".join(comment_lines),
            show_to_operator=["level_status_report", "ring_history"],
        )

        ring.overdraw_amount += int(quantity)
        ring.save()

        return Response({'msg': {'body': 'Overdraw recorded', 'type': 'success'}}, status=status.HTTP_201_CREATED)
