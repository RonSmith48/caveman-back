from django.contrib import admin
from whatif.models import Scenario, SchedSim


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ('scenario', 'name', 'owner', 'datetime_stamp')
    # Assuming RemoteUser has an email field
    search_fields = ('name', 'owner__email')
    list_filter = ('datetime_stamp',)


@admin.register(SchedSim)
class SchedSimAdmin(admin.ModelAdmin):
    list_display = (
        'bogging_block', 'production_ring', 'get_scenario_id',
        'blastsolids_id', 'start_date', 'finish_date'
    )
    search_fields = ('blastsolids_id', 'scenario__name',
                     'bogging_block__name', 'production_ring__name')
    list_filter = ('start_date', 'finish_date', 'scenario')

    # Optional: Display related fields for easier viewing in the admin interface
    raw_id_fields = ('bogging_block', 'production_ring', 'scenario')

    # Custom method to display the scenario's ID
    def get_scenario_id(self, obj):
        return obj.scenario.scenario  # Accessing the 'scenario' field from the Scenario model

    get_scenario_id.short_description = 'Scenario ID'
