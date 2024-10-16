from datetime import datetime, date, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.db import connections
import settings.models as sm
import logging


class Shkey(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def format_shkey_yr_first(shkey):
        '''
        Output yyyy-mm-dd [shift]
        '''
        if shkey[9] == "2":
            shft = " NS"
        else:
            shft = " DS"

        shift = shkey[0:4] + "-" + shkey[4:6] + "-" + shkey[6:8] + shft
        return shift

    @staticmethod
    def format_shkey_day_first(shkey):
        '''
        Output dd-mm-yyyy [shift]
        '''
        if shkey[9] == "2":
            shft = " NS"
        else:
            shft = " DS"

        shift = shkey[6:8] + "-" + shkey[4:6] + "-" + shkey[0:4] + shft
        return shift

    @staticmethod
    def generate_shkey(date1=None, dn=None):
        '''
        accepts date object or string variations
        '''
        date2 = None
        if not dn or (dn[0].upper() not in ["N", "D"]):
            dn = "D"
        if not date1:
            return ''
        elif isinstance(date1, str):
            # Detect date format
            formats_to_try = ["%d-%b-%y", "%Y-%m-%d",
                              "%y-%m-%d", "%d-%m-%y", "%d-%m-%Y"]
            for fmt in formats_to_try:
                try:
                    date2 = datetime.strptime(date1, fmt).date()
                    break
                except ValueError:
                    pass

            if not date2:
                return ''
        elif isinstance(date1, date):
            date2 = date1
        else:
            return ''

        shift = "P2" if dn[0].upper() == "N" else "P1"
        formatted = date2.strftime("%Y%m%d") + shift
        return formatted

    @staticmethod
    def shkey_to_shift(shkey):
        if shkey is None or len(shkey) != 10:
            raise ValueError(
                "Invalid input: The input string must be exactly 10 characters long.")

        year = shkey[:4]
        month = shkey[4:6]
        day = shkey[6:8]
        final_digit = shkey[9]

        formatted_date = f"{year}-{month}-{day} "

        if final_digit == "2":
            formatted_date += "NS"
        else:
            formatted_date += "DS"

        return formatted_date

    @staticmethod
    def next_shkey(shkey):
        try:
            d = shkey[:-2]
            date_obj = datetime.strptime(d, "%Y%m%d").date()
        except ValueError:
            return None

        if shkey[9] == '1':
            return d + 'P2'
        else:
            next_day = date_obj + timedelta(days=1)
            return next_day.strftime("%Y%m%d") + "P1"

    @staticmethod
    def prev_shkey(shkey):
        try:
            d = shkey[:-2]
            date_obj = datetime.strptime(d, "%Y%m%d").date()
        except ValueError:
            return None

        if shkey[9] == '2':
            return d + 'P1'
        else:
            next_day = date_obj - timedelta(days=1)
            return next_day.strftime("%Y%m%d") + "P2"