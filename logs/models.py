from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ErrorLog(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL)
    additional_info = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    error_message = models.TextField()
    stack_trace = models.TextField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"Error at {self.timestamp} - {self.error_message[:50]}"


class WarningLog(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL)
    additional_info = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    warning_message = models.TextField()
    url = models.URLField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"Warning at {self.timestamp} - {self.warning_message[:50]}"


class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    activity_type = models.CharField(max_length=50)
    description = models.TextField()  # Details about the activity
    url = models.URLField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"Activity by {self.user} at {self.timestamp} - {self.activity_type}"
