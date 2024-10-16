from rest_framework import serializers
from prod_actual.models import ProductionRing


class ProdRingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionRing
        fields = '__all__'  # Include all fields for now, or specify specific fields as needed

    def create(self, validated_data):
        # Custom creation logic if needed
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Custom update logic if needed
        return super().update(instance, validated_data)


class SingleFileSerializer(serializers.Serializer):
    file = serializers.FileField()
