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


class SchedSim(models.Model):
    bogging_block = models.ForeignKey(
        FlowModelConceptRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sim_bogging_block'
    )
    # The schedule is giving bog block so prod_ring will be set to bog ring
    production_ring = models.ForeignKey(
        ProductionRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sim_prod_rings'
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,  # Delete related SchedSim records
        null=True,
        blank=True,
        related_name='simulators'
    )
    last_drill_block = models.ForeignKey(
        FlowModelConceptRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sim_drill_block'
    )
    last_charge_block = models.ForeignKey(
        FlowModelConceptRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sim_charge_block'
    )
    sum_drill_mtrs_from_prev = models.IntegerField(blank=True, null=True)
    sum_drill_rings_from_prev = models.IntegerField(blank=True, null=True)
    sum_tonnes_from_prev = models.IntegerField(blank=True, null=True)
    sum_charged_rings_from_prev = models.IntegerField(blank=True, null=True)
    blastsolids_id = models.CharField(max_length=30, blank=True, null=True) # for bog location only
    start_date = models.DateField(blank=True, null=True)
    finish_date = models.DateField(blank=True, null=True)
    sequence = models.IntegerField(blank=True, null=True)
    mining_direction = models.CharField(max_length=2, blank=True, null=True)
    json = JSONField(blank=True, null=True)
    level = models.SmallIntegerField()
    description = models.CharField(max_length=50, blank=True, null=True)

