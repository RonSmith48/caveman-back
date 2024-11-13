from django.contrib import admin
import prod_concept.models as m


class ProdConceptAdmin(admin.ModelAdmin):
    list_display = ['description']
    search_fields = ('description', 'level')

class MiningDirectionAdmin(admin.ModelAdmin):
    list_display = ('description', 'alias', 'mining_direction', 'first_block', 'last_block')
    search_fields = ('description', 'alias', 'mining_direction')
    list_filter = ('mining_direction',)


admin.site.register(m.FlowModelConceptRing, ProdConceptAdmin)
admin.site.register(m.MiningDirection, MiningDirectionAdmin)
