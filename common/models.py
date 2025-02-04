from django.db import models
from django.db.models import JSONField


class Location(models.Model):
    location_id = models.BigAutoField(primary_key=True)
    description = models.CharField(max_length=50, blank=True, null=True)
    alias = models.CharField(max_length=50, blank=True, null=True)
    # P:Prod, D:Dev, C:Concept, I:Infrastructure
    prod_dev_code = models.CharField(max_length=1, blank=True)
    is_active = models.BooleanField(blank=True, null=True, default=True)
    comment = models.TextField(blank=True, null=True)
    level = models.SmallIntegerField()
    cable_bolted = models.BooleanField(default=False)
    area_rehab = models.BooleanField(default=False)
    fault = models.BooleanField(default=False)
    status = models.CharField(max_length=50, blank=True, null=True)
    x = models.DecimalField(max_digits=12, decimal_places=6)
    y = models.DecimalField(max_digits=12, decimal_places=6)
    z = models.DecimalField(max_digits=12, decimal_places=6)

    def __str__(self):
        return self.description if self.description else f'Location {self.location_id}'

    class Meta:
        abstract = True


class Reference(models.Model):
    name = models.CharField(max_length=255)
    # store json report
    report = JSONField(blank=True, null=True)
    # takes shkey
    for_date = models.CharField(max_length=10, blank=True, null=True)
    expiry = models.CharField(max_length=10, blank=True, null=True)
    datetime_stamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
