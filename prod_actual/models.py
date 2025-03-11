from django.db import models
from django.db.models import JSONField
from users.models import CustomUser
from common.models import Location
from common.functions.constants import MANDATORY_RING_STATES
from prod_concept.models import FlowModelConceptRing
import json


class ProductionRing(Location):
    concept_ring = models.ForeignKey(
        FlowModelConceptRing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='production_rings'
    )
    oredrive = models.CharField(max_length=50)
    ring_number_txt = models.CharField(max_length=10, blank=True, null=True)
    dump = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True)
    azimuth = models.DecimalField(
        max_digits=7, decimal_places=4, blank=True, null=True)
    burden = models.CharField(max_length=10, blank=True, null=True)
    holes = models.SmallIntegerField(blank=True, null=True)
    diameters = models.CharField(max_length=30, blank=True, null=True)
    drill_meters = models.DecimalField(
        max_digits=8, decimal_places=4, blank=True, null=True)
    drill_look_direction = models.CharField(
        max_length=10, blank=True, null=True)
    designed_to_suit = models.CharField(
        max_length=30, blank=True, null=True)  # Rig: Solo or Simba
    drilled_meters = models.DecimalField(
        max_digits=7, decimal_places=4, blank=True, null=True)
    drill_complete_shift = models.CharField(
        max_length=10, blank=True, null=True)
    charge_shift = models.CharField(max_length=10, blank=True, null=True)
    detonator_designed = models.CharField(max_length=50, blank=True, null=True)
    detonator_actual = models.CharField(max_length=50, blank=True, null=True)
    designed_emulsion_kg = models.SmallIntegerField(blank=True, null=True)
    design_date = models.CharField(max_length=10, blank=True, null=True)
    markup_date = models.CharField(max_length=10, blank=True, null=True)
    fireby_date = models.CharField(max_length=10, blank=True, null=True)
    fired_shift = models.CharField(max_length=10, blank=True, null=True)
    multi_fire_group = models.CharField(max_length=10, blank=True, null=True)
    bog_complete_shift = models.CharField(max_length=10, blank=True, null=True)
    markup_for = models.CharField(max_length=50, blank=True, null=True)
    blastsolids_volume = models.DecimalField(
        max_digits=10, decimal_places=4, blank=True, null=True)
    mineral3 = models.DecimalField(
        max_digits=6, decimal_places=4, blank=True, null=True)
    mineral4 = models.DecimalField(
        max_digits=6, decimal_places=4, blank=True, null=True)
    designed_tonnes = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, null=False)  # in situ tonnes
    draw_percentage = models.DecimalField(
        max_digits=7, decimal_places=4, default=0, null=False)
    overdraw_amount = models.SmallIntegerField(default=0)
    draw_deviation = models.DecimalField(
        max_digits=6, decimal_places=1, default=0)
    bogged_tonnes = models.DecimalField(
        max_digits=6, decimal_places=1, default=0)
    hole_data = JSONField(blank=True, null=True)
    dist_to_wop = models.DecimalField(
        max_digits=6, decimal_places=1, blank=True, null=True)
    dist_to_eop = models.DecimalField(
        max_digits=6, decimal_places=1, blank=True, null=True)
    has_pyrite = models.BooleanField(default=False)
    in_water_zone = models.BooleanField(default=False)
    is_making_water = models.BooleanField(default=False)
    in_overdraw_zone = models.BooleanField(
        default=False, blank=True, null=True)
    in_flow = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.level} {self.oredrive} {self.ring_number_txt}'

    def set_hole_data(self, data):
        self.hole_data = data

    def get_hole_data(self):
        return self.hole_data

    class Meta:
        verbose_name_plural = 'Production Rings'
        ordering = ['level', 'oredrive']


class BoggedTonnes(models.Model):
    # Data is duplicated from pitram, intentionally
    # we must allow for manual entries
    production_ring = models.ForeignKey(
        ProductionRing,
        on_delete=models.CASCADE,
        related_name='bogging_tonnes'
    )
    bogged_tonnes = models.DecimalField(
        max_digits=6, decimal_places=1, default=0)
    shkey = models.CharField(max_length=10)
    entered_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True)
    datetime_stamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Bogged Tonnes"


class MultifireGroup(models.Model):
    """
    For managing ring groups and super groups
    """
    multifire_group_id = models.BigAutoField(primary_key=True)
    is_active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    level = models.SmallIntegerField()
    total_volume = models.FloatField(blank=True, null=True)
    total_tonnage = models.FloatField(blank=True, null=True)
    avg_density = models.FloatField(blank=True, null=True)
    avg_au = models.FloatField(blank=True, null=True)
    avg_cu = models.FloatField(blank=True, null=True)
    pooled_rings = models.JSONField()
    group_rings = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    entered_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='mf_creator')
    # In actual fact, this should be called a deletion, custom rings are deleted.
    # This is a record of who deleted and when.
    deactivated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='mf_deactivator')
    updated_at = models.DateTimeField(auto_now=True)


class RingComments(models.Model):
    ring_id = models.ForeignKey(ProductionRing, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    deactivated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='editor')
    department = models.CharField(max_length=50)
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='author')
    datetime = models.DateTimeField(auto_now_add=True)
    comment = models.TextField()
    # eg. driller, loader, chargeup
    show_to_operator = models.CharField(max_length=50, blank=True, null=True)


class RingState(models.Model):
    pri_state = models.CharField(max_length=30)
    sec_state = models.CharField(max_length=30, blank=True, null=True)

    def __str__(self):
        return f"{self.pri_state} - {self.sec_state or 'None'}"

    def delete(self, *args, **kwargs):
        if {"pri_state": self.pri_state, "sec_state": self.sec_state} in MANDATORY_RING_STATES:
            raise ValueError("Cannot delete mandatory RingState.")
        super().delete(*args, **kwargs)


class RingStateChange(models.Model):
    ring_state_id = models.BigAutoField(primary_key=True)
    is_active = models.BooleanField(default=True)
    deactivated_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='change_deactivation', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    prod_ring = models.ForeignKey(ProductionRing, on_delete=models.CASCADE)
    shkey = models.CharField(max_length=20, blank=True, null=True)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='change_activation', blank=True, null=True)
    # This is a secondary state, a tag
    state = models.ForeignKey(RingState, on_delete=models.CASCADE)
    comment = models.TextField(blank=True, null=True)
    operation_complete = models.BooleanField(default=True)
    mtrs_drilled = models.DecimalField(
        max_digits=5, decimal_places=1, default=0)
    holes_completed = models.SmallIntegerField(blank=True, null=True)
    detail = models.JSONField(blank=True, null=True)


class RingLink(models.Model):
    ring = models.ForeignKey(
        ProductionRing, on_delete=models.CASCADE, related_name='linked_ring')
    linked = models.ForeignKey(
        ProductionRing, on_delete=models.CASCADE, related_name='linked')
    direction = models.CharField(max_length=1, choices=[
        ('P', 'Predecessor'),
        ('S', 'Successor')
    ], null=True, blank=True)
