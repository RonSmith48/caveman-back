from django.contrib import admin
import prod_concept.models as m


class ProdConceptAdmin(admin.ModelAdmin):
    list_display = ['description']
    search_fields = ('description', 'level')


admin.site.register(m.FlowModelConceptRing, ProdConceptAdmin)
