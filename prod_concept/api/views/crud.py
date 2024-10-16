from rest_framework import generics
import prod_concept.models as m
import prod_concept.api.serializers as s


class ConceptRingListCreateView(generics.ListCreateAPIView):
    queryset = m.FlowModelConceptRing.objects.all()
    serializer_class = s.ConceptRingSerializer


class ConceptRingRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = m.FlowModelConceptRing.objects.all()
    serializer_class = s.ConceptRingSerializer


class ConceptRingStatusListView(generics.ListAPIView):
    serializer_class = s.ConceptRingSerializer

    def get_queryset(self):
        status = self.kwargs['status']
        return m.FlowModelConceptRing.objects.filter(status=status)
