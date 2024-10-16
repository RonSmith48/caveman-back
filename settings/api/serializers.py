from rest_framework import serializers
import settings.models as m


class PitramConnectionSerializer(serializers.ModelSerializer):
    database_type = serializers.CharField(max_length=50)
    ip_address = serializers.CharField(max_length=100)
    port = serializers.IntegerField()
    username = serializers.CharField(max_length=100)
    # Don't return the password in the response
    password = serializers.CharField(max_length=100, write_only=True)
    database_name = serializers.CharField(max_length=100)

    class Meta:
        model = m.ProjectSetting
        fields = ['key', 'database_type', 'ip_address',
                  'port', 'username', 'password', 'database_name']

    def create(self, validated_data):
        # Prepare the JSON value for storing connection details
        connection_details = {
            "database_type": validated_data['database_type'],
            "ip_address": validated_data['ip_address'],
            "port": validated_data['port'],
            "username": validated_data['username'],
            # Store encrypted or masked in practice
            "password": validated_data['password'],
            "database_name": validated_data['database_name'],
        }

        setting = m.ProjectSetting.objects.create(
            key=validated_data['key'],
            value=connection_details
        )
        return setting

    def update(self, instance, validated_data):
        # Update the JSON value for storing connection details
        connection_details = instance.value
        connection_details.update({
            "database_type": validated_data.get('database_type', connection_details.get('database_type')),
            "ip_address": validated_data.get('ip_address', connection_details.get('ip_address')),
            "port": validated_data.get('port', connection_details.get('port')),
            "username": validated_data.get('username', connection_details.get('username')),
            # Store encrypted or masked in practice
            "password": validated_data.get('password', connection_details.get('password')),
            "database_name": validated_data.get('database_name', connection_details.get('database_name')),
        })

        instance.value = connection_details
        instance.save()
        return instance


class ProjectSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ProjectSetting
        # Include 'id' for identification in updates and deletions.
        fields = ['id', 'key', 'value']
