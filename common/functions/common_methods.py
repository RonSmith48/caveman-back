from django.core.exceptions import ObjectDoesNotExist
import settings.models as sm
import logging


class CommonMethods(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_setting(self, key):
        settings = sm.ProjectSetting.objects.filter(key=key)

        if not settings.exists():
            return None

        if settings.count() > 1:
            self.logger.warning(
                f"There are multiple settings with the key: {key}")

        return settings.first().value

    def number_fix(self, cell):
        if isinstance(cell, str):
            try:
                return float(cell)
            except ValueError:
                return 0
        else:
            return cell

    def no_null(self, cell):
        if cell == "":
            return 0
        else:
            return cell
