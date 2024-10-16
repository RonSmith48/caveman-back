from django.contrib import admin
import report.models as m


class JsonReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'for_date', 'expiry']
    search_fields = ('name', 'for_date', 'expiry')


admin.site.register(m.JsonReport, JsonReportAdmin)
