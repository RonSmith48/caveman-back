from django.contrib import admin
from .models import ErrorLog, WarningLog, UserActivityLog


class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'error_message', 'url', 'ip_address')
    search_fields = ('error_message', 'url', 'ip_address')
    list_filter = ('timestamp', 'user')
    readonly_fields = ('timestamp', 'error_message',
                       'stack_trace', 'url', 'ip_address', 'user')


class WarningLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user',
                    'warning_message', 'url', 'ip_address')
    search_fields = ('warning_message', 'url', 'ip_address')
    list_filter = ('timestamp', 'user')
    readonly_fields = ('timestamp', 'warning_message',
                       'url', 'ip_address', 'user')


class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'activity_type',
                    'url', 'ip_address', 'description')
    search_fields = ('activity_type', 'url', 'user', 'description')
    list_filter = ('timestamp', 'user', 'activity_type')
    readonly_fields = ('timestamp', 'description', 'url',
                       'ip_address', 'activity_type', 'user')


admin.site.register(ErrorLog, ErrorLogAdmin)
admin.site.register(WarningLog, WarningLogAdmin)
admin.site.register(UserActivityLog, UserActivityLogAdmin)
