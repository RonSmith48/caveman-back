from django.db import models
from django.db.models import JSONField
from users.models import CustomUser
from common.models import Location
from prod_actual.models import ProductionRing
from prod_concept.models import FlowModelConceptRing
import json

# Create your models here.


class Scenario(models.Model):
    scenario = models.AutoField(primary_key=True)
    name = models.CharField(max_length=20, blank=True, null=True)
    owner = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True)
    datetime_stamp = models.DateTimeField(auto_now_add=True)
    json = JSONField(blank=True, null=True)


class ScheduleSimulator(Location):
    concept_ring = models.ForeignKey(
        FlowModelConceptRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sim_concept_rings'
    )
    production_ring = models.ForeignKey(
        ProductionRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sim_prod_rings'
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,  # Delete related ScheduleSimulator records
        null=True,
        blank=True,
        related_name='simulators'
    )
    blastsolids_id = models.CharField(max_length=30)
    start_date = models.DateField(blank=True, null=True)
    finish_date = models.DateField(blank=True, null=True)
    sequence = models.IntegerField(blank=True, null=True)
    mining_direction = models.CharField(max_length=2, blank=True, null=True)
    json = JSONField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Check for duplicate blastsolids_id within the same scenario
        if not ScheduleSimulator.objects.filter(
            blastsolids_id=self.blastsolids_id, scenario=self.scenario
        ).exists():
            super(ScheduleSimulator, self).save(*args, **kwargs)
        # Optional: Log or ignore duplicates silently
