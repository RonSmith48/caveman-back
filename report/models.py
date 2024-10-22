from django.db import models, transaction
from django.db.models import JSONField
from django.utils import timezone
from datetime import timedelta


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


class Lock(models.Model):
    item = models.CharField(max_length=250, unique=True)
    locked = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    duration = models.DurationField(default=timedelta(minutes=3))

    def is_expired(self):
        expiration_time = self.timestamp + self.duration
        return expiration_time <= timezone.now()

    @classmethod
    def is_locked(cls, item_name):
        try:
            lock = cls.objects.get(item=item_name)
            return lock.locked
        except cls.DoesNotExist:
            return False

    @classmethod
    def get_lock(cls, item_name):
        lock, created = cls.objects.get_or_create(item=item_name)
        return lock

    @classmethod
    def set_lock(cls, item_name):
        with transaction.atomic():
            lock, created = cls.objects.get_or_create(item=item_name)
            if lock.locked:
                return False  # Lock is already in use
            lock.locked = True
            lock.save()
            return True  # Lock set successfully

    @classmethod
    def remove_lock(cls, item_name):
        with transaction.atomic():
            try:
                lock = cls.objects.get(item=item_name)
                lock.delete()
                return True  # Lock removed successfully
            except cls.DoesNotExist:
                return False  # Lock not found
