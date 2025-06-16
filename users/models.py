from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
# from django.utils.translation import gettext_lazy as _


class RemoteUserManager(BaseUserManager):
    def create_user(self, *args, **kwargs):
        raise NotImplementedError(
            "Local user creation is disabled—accounts live only on the auth server."
        )

    def create_superuser(self, *args, **kwargs):
        raise NotImplementedError(
            "Superuser creation is disabled—accounts live only on the auth server."
        )


class RemoteUser(AbstractBaseUser, PermissionsMixin):
    """
    A local “mirror” of the CustomUser living on the auth server.
    We only keep the fields we display frequently, and track a last‐updated timestamp.
    """
    id = models.PositiveBigIntegerField(
        primary_key=True,
        editable=False,
        help_text="Primary key from the auth‐server’s CustomUser"
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    initials = models.CharField(max_length=3, null=True, blank=True)
    email = models.CharField(max_length=255, unique=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    start_date = models.DateTimeField(default=timezone.now)
    role = models.CharField(max_length=30, null=True, blank=True)
    permissions = models.JSONField(null=True, blank=True)
    avatar = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.first_name + ' ' + self.last_name

    def __str__(self):
        return self.email

    @property
    def is_authenticated(self):
        """
        Always return True, as this model is a mirror of the auth server's user.
        """
        return True

    @property
    def is_anonymous(self):
        """
        Always return False, as this model is a mirror of the auth server's user.
        """
        return False
