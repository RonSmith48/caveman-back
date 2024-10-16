from django.contrib import admin
from .models import ProjectSetting


class ProjectSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'get_value_type', 'get_value_preview')
    search_fields = ('key',)
    readonly_fields = ('key',)

    def get_value_type(self, obj):
        if isinstance(obj.value, dict) and 'type' in obj.value:
            return obj.value['type']
        return 'Unknown'

    get_value_type.short_description = 'Value Type'

    def get_value_preview(self, obj):
        if isinstance(obj.value, dict) and 'value' in obj.value:
            value_preview = str(obj.value['value'])
            return value_preview if len(value_preview) <= 50 else value_preview[:47] + '...'
        return 'No value'

    get_value_preview.short_description = 'Value Preview'


admin.site.register(ProjectSetting, ProjectSettingAdmin)
