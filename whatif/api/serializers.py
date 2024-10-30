from rest_framework import serializers

class SingleFileSerializer(serializers.Serializer):
    file = serializers.FileField()