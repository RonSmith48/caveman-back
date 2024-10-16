from django.contrib import admin
import prod_actual.models as m


class ProdActualAdmin(admin.ModelAdmin):
    list_display = ['alias', 'description']
    search_fields = ('alias', 'description', 'level')


class BoggedTonnesAdmin(admin.ModelAdmin):
    list_display = ['shkey', 'get_production_ring_alias', 'bogged_tonnes']
    search_fields = ('shkey',)

    def get_production_ring_alias(self, obj):
        return obj.production_ring.alias
    get_production_ring_alias.short_description = 'Production Ring Alias'


admin.site.register(m.ProductionRing, ProdActualAdmin)
admin.site.register(m.BoggedTonnes, BoggedTonnesAdmin)
