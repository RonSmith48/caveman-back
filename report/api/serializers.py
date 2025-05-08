# serializers.py
from rest_framework import serializers
from prod_actual.models import ProductionRing


class DataDupeSerializer(serializers.ModelSerializer):
    description = serializers.CharField(label='Description')
    alias = serializers.CharField(label='Alias')
    prod_dev_code = serializers.CharField(label='Prod/Dev Code')
    level = serializers.IntegerField(label='Level')
    cable_bolted = serializers.BooleanField(label='Cable Bolted')
    area_rehab = serializers.BooleanField(label='Area Rehab')
    fault = serializers.BooleanField(label='Fault')
    status = serializers.CharField(label='Status')
    x = serializers.DecimalField(max_digits=12, decimal_places=6, label='X')
    y = serializers.DecimalField(max_digits=12, decimal_places=6, label='Y')
    z = serializers.DecimalField(max_digits=12, decimal_places=6, label='Z')
    oredrive = serializers.CharField(label='Ore Drive')
    ring_number_txt = serializers.CharField(label='Ring Number')
    dump = serializers.DecimalField(
        max_digits=4, decimal_places=1, label='Dump')
    azimuth = serializers.DecimalField(
        max_digits=7, decimal_places=4, label='Azimuth')
    burden = serializers.CharField(label='Burden')
    holes = serializers.IntegerField(label='Holes')
    diameters = serializers.CharField(label='Diameters')
    drill_meters = serializers.DecimalField(
        max_digits=8, decimal_places=4, label='Drill Meters')
    drill_look_direction = serializers.CharField(label='Drill Look Direction')
    designed_to_suit = serializers.CharField(label='Designed To Suit')
    drilled_meters = serializers.DecimalField(
        max_digits=7, decimal_places=4, label='Drilled Meters')
    drill_complete_shift = serializers.CharField(label='Drill Complete Shift')
    charge_shift = serializers.CharField(label='Charge Shift')
    detonator_designed = serializers.CharField(label='Detonator Designed')
    detonator_actual = serializers.CharField(label='Detonator Actual')
    designed_emulsion_kg = serializers.IntegerField(
        label='Designed Emulsion (kg)')
    design_date = serializers.CharField(label='Design Date')
    markup_date = serializers.CharField(label='Markup Date')
    fireby_date = serializers.CharField(label='Fire By Date')
    fired_shift = serializers.CharField(label='Fired Shift')
    multi_fire_group = serializers.CharField(label='Multi-fire Group')
    bog_complete_shift = serializers.CharField(label='Bog Complete Shift')
    markup_for = serializers.CharField(label='Markup For')
    blastsolids_volume = serializers.DecimalField(
        max_digits=10, decimal_places=4, label='Blast Solids Volume')
    mineral3 = serializers.DecimalField(
        max_digits=6, decimal_places=4, label='Mineral 3')
    mineral4 = serializers.DecimalField(
        max_digits=6, decimal_places=4, label='Mineral 4')
    designed_tonnes = serializers.DecimalField(
        max_digits=10, decimal_places=2, label='Designed Tonnes')
    draw_percentage = serializers.DecimalField(
        max_digits=7, decimal_places=4, label='Draw %')
    overdraw_amount = serializers.IntegerField(label='Overdraw Amount')
    draw_deviation = serializers.DecimalField(
        max_digits=6, decimal_places=1, label='Draw Deviation')
    bogged_tonnes = serializers.DecimalField(
        max_digits=6, decimal_places=1, label='Bogged Tonnes')
    dist_to_wop = serializers.DecimalField(
        max_digits=6, decimal_places=1, label='Distance to WOP')
    dist_to_eop = serializers.DecimalField(
        max_digits=6, decimal_places=1, label='Distance to EOP')
    has_pyrite = serializers.BooleanField(label='Has Pyrite')
    in_water_zone = serializers.BooleanField(label='In Water Zone')
    is_making_water = serializers.BooleanField(label='Is Making Water')
    in_overdraw_zone = serializers.BooleanField(label='In Overdraw Zone')
    in_flow = serializers.BooleanField(label='In Flow')

    class Meta:
        model = ProductionRing
        fields = [
            'description', 'level', 'oredrive', 'ring_number_txt', 'alias', 'status', 'x', 'y', 'z',
            'prod_dev_code', 'cable_bolted', 'area_rehab', 'fault', 'dump', 'azimuth', 'burden', 'holes',
            'diameters', 'drill_meters', 'drill_look_direction', 'designed_to_suit',
            'drilled_meters', 'drill_complete_shift', 'charge_shift',
            'detonator_designed', 'detonator_actual', 'designed_emulsion_kg',
            'design_date', 'markup_date', 'fireby_date', 'fired_shift',
            'bog_complete_shift', 'markup_for', 'blastsolids_volume',
            'designed_tonnes', 'draw_percentage', 'overdraw_amount', 'draw_deviation', 'bogged_tonnes',
            'has_pyrite', 'in_water_zone', 'is_making_water',
            'in_overdraw_zone', 'in_flow'
        ]
