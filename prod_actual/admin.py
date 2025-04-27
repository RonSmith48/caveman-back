from django.contrib import admin
import prod_actual.models as m


class ProdActualAdmin(admin.ModelAdmin):
    list_display = ['alias', 'description', 'location_id']
    search_fields = ('alias', 'description', 'level')


class BoggedTonnesAdmin(admin.ModelAdmin):
    list_display = ['shkey', 'get_production_ring_alias', 'bogged_tonnes']
    search_fields = ('shkey',)

    def get_production_ring_alias(self, obj):
        return obj.production_ring.alias
    get_production_ring_alias.short_description = 'Production Ring Alias'


class MultifireGroupAdmin(admin.ModelAdmin):
    list_display = ('multifire_group_id', 'name', 'level', 'is_active',
                    'total_tonnage', 'total_volume', 'created_at', 'entered_by', 'deactivated_by')
    list_filter = ('is_active', 'level', 'created_at')
    search_fields = ('name', 'entered_by__username',
                     'deactivated_by__username')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('General Info', {
            'fields': ('name', 'level', 'is_active')
        }),
        ('Statistics', {
            'fields': ('total_volume', 'total_tonnage', 'avg_density', 'avg_au', 'avg_cu')
        }),
        ('Rings Data', {
            'fields': ('pooled_rings', 'group_rings')
        }),
        ('Timestamps & Users', {
            'fields': ('created_at', 'updated_at', 'entered_by', 'deactivated_by')
        }),
    )


class DrawChangeAdmin(admin.ModelAdmin):
    list_display = (
        'ring', 'type', 'quantity', 'user', 'status',
        'created_at', 'updated_at',
    )
    list_filter = ('type', 'status', 'user', 'created_at')
    search_fields = ('ring__description', 'ring__oredrive',
                     'user__username', 'reason')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {
            'fields': ('ring', 'type', 'quantity', 'user', 'reason', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_active', 'approvers'),
            'classes': ('collapse',),
        }),
    )


admin.site.register(m.DrawChange, DrawChangeAdmin)
admin.site.register(m.ProductionRing, ProdActualAdmin)
admin.site.register(m.BoggedTonnes, BoggedTonnesAdmin)
admin.site.register(m.MultifireGroup, MultifireGroupAdmin)
