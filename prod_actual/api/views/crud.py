from rest_framework import generics
import prod_actual.models as m
import prod_actual.api.serializers as s


class ProdRingListCreateView(generics.ListCreateAPIView):
    queryset = m.ProductionRing.objects.all()
    serializer_class = s.ProdRingSerializer


class ProdRingRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = m.ProductionRing.objects.all()
    serializer_class = s.ProdRingSerializer


class ProdRingStatusListView(generics.ListAPIView):
    serializer_class = s.ProdRingSerializer

    def get_queryset(self):
        status = self.kwargs['status']
        return m.ProductionRing.objects.filter(status=status)
