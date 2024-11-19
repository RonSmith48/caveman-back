from django.contrib import admin
import prod_concept.models as m


class ProdConceptAdmin(admin.ModelAdmin):
    list_display = ['description', 'blastsolids_id']
    search_fields = ('description', 'level')


class MiningDirectionAdmin(admin.ModelAdmin):
    list_display = ('description', 'alias', 'mining_direction',
                    'first_block', 'last_block')
    search_fields = ('description', 'alias', 'mining_direction')
    list_filter = ('mining_direction',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ['first_block', 'last_block']:
            kwargs["queryset"] = m.FlowModelConceptRing.objects.order_by(
                'blastsolids_id')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(m.FlowModelConceptRing, ProdConceptAdmin)
admin.site.register(m.MiningDirection, MiningDirectionAdmin)
