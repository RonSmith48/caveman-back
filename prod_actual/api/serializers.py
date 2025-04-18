from rest_framework import serializers
from common.functions.constants import MANDATORY_RING_STATES
import prod_actual.models as m


class ProdRingSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ProductionRing
        exclude = ['concept_ring']

    def create(self, validated_data):
        # Custom creation logic if needed
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Custom update logic if needed
        return super().update(instance, validated_data)


class RingStateChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.RingStateChange
        exclude = ['deactivated_by', 'prod_ring', 'user', 'state']


class SingleFileSerializer(serializers.Serializer):
    file = serializers.FileField()


class BoggedTonnesSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.BoggedTonnes
        fields = ['id', 'production_ring', 'bogged_tonnes',
                  'shkey', 'entered_by', 'datetime_stamp']


class RingStateSerializer(serializers.ModelSerializer):
    is_mandatory = serializers.SerializerMethodField()

    class Meta:
        model = m.RingState
        fields = ["id", "pri_state", "sec_state", "is_mandatory"]

    def get_is_mandatory(self, obj):
        return {"pri_state": obj.pri_state, "sec_state": obj.sec_state} in MANDATORY_RING_STATES


class ProductionRingReportSerializer(serializers.ModelSerializer):
    cu_pct = serializers.DecimalField(
        max_digits=5, decimal_places=3, source='concept_ring.modelled_cu', read_only=True)
    au_gram_per_tonne = serializers.DecimalField(
        max_digits=5, decimal_places=3, source='concept_ring.modelled_au', read_only=True)
    density = serializers.DecimalField(
        max_digits=4, decimal_places=3, source='concept_ring.density', read_only=True)

    class Meta:
        model = m.ProductionRing
        fields = [
            'location_id', 'level', 'oredrive', 'ring_number_txt', 'holes', 'drill_meters',
            'azimuth', 'dump', 'burden', 'diameters',
            'cu_pct', 'au_gram_per_tonne', 'density',
            'blastsolids_volume', 'designed_tonnes', 'draw_percentage', 'x', 'y', 'z'
        ]
