from rest_framework import serializers
import prod_actual.models as m


class ProdRingSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ProductionRing
        fields = '__all__'  # Include all fields for now, or specify specific fields as needed

    def create(self, validated_data):
        # Custom creation logic if needed
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Custom update logic if needed
        return super().update(instance, validated_data)


class SingleFileSerializer(serializers.Serializer):
    file = serializers.FileField()


class BoggedTonnesSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.BoggedTonnes
        fields = ['id', 'production_ring', 'bogged_tonnes',
                  'shkey', 'entered_by', 'datetime_stamp']
