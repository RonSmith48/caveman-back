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
