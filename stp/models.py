from django.db import models
from django.db.models import JSONField
from users.models import RemoteUser
from common.models import Location
from prod_actual.models import ProductionRing
from prod_concept.models import FlowModelConceptRing


class TmrpSchedule(models.Model):
    schedule = models.AutoField(primary_key=True)
    name = models.CharField(max_length=20, blank=True, null=True)
    owner = models.ForeignKey(
        RemoteUser, on_delete=models.SET_NULL, blank=True, null=True)
    datetime_stamp = models.DateTimeField(auto_now_add=True)
    json = JSONField(blank=True, null=True)


class ConsumptionSchedule(Location):
    concept_ring = models.ForeignKey(
        FlowModelConceptRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tmrp_concept_rings'
    )
    production_ring = models.ForeignKey(
        ProductionRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tmrp_prod_rings'
    )
    schedule = models.ForeignKey(
        TmrpSchedule,
        on_delete=models.CASCADE,  # Delete related Schedule records
        null=True,
        blank=True,
        related_name='tmrp_schedule'
    )
    blastsolids_id = models.CharField(max_length=30)
    start_date = models.CharField(max_length=10, blank=True, null=True)
    finish_date = models.CharField(max_length=10, blank=True, null=True)
    sequence = models.IntegerField(blank=True, null=True)
    mining_direction = models.CharField(max_length=2, blank=True, null=True)
    json = JSONField(blank=True, null=True)
