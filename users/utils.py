
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from users.models import RemoteUser

# How often you consider a local copy “stale” (you can ignore TTL if you only
# want to fetch-once). For now, set it very long (e.g. 1 day):
USER_CACHE_TTL = timedelta(days=1)


def fetch_user_from_auth_server(user_id):
    """
    Call GET <AUTH_SERVER_URL>/api/users/<user_id>/,
    return the JSON dict, or None on failure.
    """
    url = f"{settings.AUTH_SERVER_URL.rstrip('/')}/users/{user_id}/"
    try:
        resp = requests.get(url, timeout=3.0)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    return resp.json()


def get_or_create_remote_user(user_id):
    """
    Return a RemoteUser for this ID. If no local row exists, or if it's older
    than USER_CACHE_TTL, fetch from auth server and save.
    """
    try:
        user = RemoteUser.objects.get(pk=user_id)
    except RemoteUser.DoesNotExist:
        user = None

    need_fetch = (user is None or (timezone.now() -
                  user.updated_at) > USER_CACHE_TTL)

    if need_fetch:
        data = fetch_user_from_auth_server(user_id)
        if not data:
            # Auth server couldn’t return a user → we give up (user stays None)
            return user

        # Map JSON from auth to your RemoteUser fields:
        avatar = data.get('avatar', {}) or {}
        defaults = {
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'initials': data.get('initials', ''),
            'email': data.get('email', ''),
            'is_staff': data.get('is_staff', False),
            'is_active': data.get('is_active', True),
            'is_superuser': data.get('is_superuser', False),
            'start_date': data.get('start_date', None),
            'role': data.get('role', None),
            'permissions': data.get('permissions', {}),
            'avatar': data.get('avatar', None),
        }

        # Create or update the local mirror row:
        user, _ = RemoteUser.objects.update_or_create(
            pk=user_id, defaults=defaults)

    return user
