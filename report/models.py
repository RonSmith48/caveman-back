from django.db import models
from django.db.models import JSONField


class JsonReport(models.Model):
    name = models.CharField(max_length=255)
    # store json report
    report = JSONField()
    # takes shkey
    for_date = models.CharField(max_length=10, blank=True, null=True)
    expiry = models.CharField(max_length=10, blank=True, null=True)
    datetime_stamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
