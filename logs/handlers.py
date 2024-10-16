import logging
import sys
from django.core.management import call_command
from django.db import connections
from django.utils.timezone import now
from django.apps import apps

logger = logging.getLogger('custom_logger')

USER_ACTIVITY_LEVEL = 25  # Custom log level between WARNING (30) and INFO (20)
logging.addLevelName(USER_ACTIVITY_LEVEL, 'USER_ACTIVITY')


def user_activity(self, message, *args, **kwargs):
    if self.isEnabledFor(USER_ACTIVITY_LEVEL):
        self._log(USER_ACTIVITY_LEVEL, message, args, **kwargs)


logging.Logger.user_activity = user_activity


class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        try:
            # Ensure the database connection is usable
            if not connections['default'].connection or not connections['default'].is_usable():
                return

            # Skip logging during certain management commands
            if 'manage.py' in sys.argv and any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'runserver']):
                return

            ErrorLog = apps.get_model('logs', 'ErrorLog')
            WarningLog = apps.get_model('logs', 'WarningLog')
            UserActivityLog = apps.get_model('logs', 'UserActivityLog')

            if record.levelname == 'ERROR':
                self._log_error(record, ErrorLog)
            elif record.levelname == 'WARNING':
                self._log_warning(record, WarningLog)
            elif record.levelname == 'USER_ACTIVITY':
                self._log_user_activity(record, UserActivityLog)
        except Exception as e:
            logging.error(f"Failed to log message to the database: {str(e)}")

    def _log_error(self, record, ErrorLog):
        ErrorLog.objects.create(
            user=self._get_user(record),
            timestamp=now(),
            error_message=record.getMessage(),
            stack_trace=self._get_stack_trace(record),
            url=self._get_url(record),
            ip_address=self._get_ip_address(record),
        )

    def _log_warning(self, record, WarningLog):
        WarningLog.objects.create(
            user=self._get_user(record),
            timestamp=now(),
            warning_message=record.getMessage(),
            url=self._get_url(record),
            ip_address=self._get_ip_address(record),
        )

    def _log_user_activity(self, record, UserActivityLog):
        UserActivityLog.objects.create(
            user=self._get_user(record),
            timestamp=now(),
            activity_type=record.getMessage(),
            description=getattr(record, 'description', ''),
            url=self._get_url(record),
            ip_address=self._get_ip_address(record),
        )

    def _get_user(self, record):
        return getattr(record, 'user', None)

    def _get_stack_trace(self, record):
        if record.exc_info:
            import traceback
            return ''.join(traceback.format_exception(*record.exc_info))
        return None

    def _get_url(self, record):
        return getattr(record, 'url', None)

    def _get_ip_address(self, record):
        return getattr(record, 'ip_address', None)
