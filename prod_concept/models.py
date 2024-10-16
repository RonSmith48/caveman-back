from django.db import models
from common.models import Location


class FlowModelConceptRing(Location):
    blastsolids_id = models.CharField(max_length=30)
    heading = models.CharField(max_length=50)
    drive = models.SmallIntegerField()
    loc = models.CharField(max_length=5)
    pgca_modelled_tonnes = models.DecimalField(max_digits=7, decimal_places=2)
    draw_zone = models.SmallIntegerField()
    density = models.DecimalField(max_digits=4, decimal_places=3)
    modelled_au = models.DecimalField(max_digits=5, decimal_places=3)
    modelled_cu = models.DecimalField(max_digits=5, decimal_places=3)

    def __str__(self):
        return self.blastsolids_id
