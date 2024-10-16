from django.db import models
from django.db.models import JSONField


class ProjectSetting(models.Model):
    # A unique key to identify each setting
    key = models.CharField(max_length=255, unique=True,
                           help_text="Unique identifier for the setting")

    # A JSON field to store the setting value along with its data type
    value = JSONField(
        help_text="Serialized JSON containing the setting value and data type")

    def __str__(self):
        return self.key

    class Meta:
        verbose_name = "App Setting"
        verbose_name_plural = "Cave Manager Settings"
