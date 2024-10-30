from django.contrib import admin
from whatif.models import Scenario, ScheduleSimulator

@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ('scenario', 'name', 'owner', 'datetime_stamp')
    search_fields = ('name', 'owner__email')  # Assuming CustomUser has an email field
    list_filter = ('datetime_stamp',)

@admin.register(ScheduleSimulator)
class ScheduleSimulatorAdmin(admin.ModelAdmin):
    list_display = (
        'location_id', 'concept_ring', 'production_ring', 'get_scenario_id',
        'blastsolids_id', 'start_date', 'finish_date'
    )
    search_fields = ('blastsolids_id', 'scenario__name', 'concept_ring__name', 'production_ring__name')
    list_filter = ('start_date', 'finish_date', 'scenario')

    # Optional: Display related fields for easier viewing in the admin interface
    raw_id_fields = ('concept_ring', 'production_ring', 'scenario')

    # Custom method to display the scenario's ID
    def get_scenario_id(self, obj):
        return obj.scenario.scenario  # Accessing the 'scenario' field from the Scenario model

    get_scenario_id.short_description = 'Scenario ID'

