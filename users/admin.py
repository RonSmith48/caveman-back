from django.contrib import admin
import users.models as m


class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'initials', 'is_active',
                    'is_staff', 'is_superuser', 'otp', 'last_login', 'start_date', 'group')
    search_fields = ('email', 'is_active', 'is_staff', 'is_superuser')

    def group(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    group.short_description = 'Groups'


admin.site.register(m.CustomUser, UserAdmin)
