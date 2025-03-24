from rest_framework import generics, status
from rest_framework.response import Response

import prod_actual.api.serializers as s
import prod_actual.models as m
import prod_concept.models as pcm

from time import strftime
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q, ExpressionWrapper
from django.db.models.functions import Abs
from datetime import datetime, timedelta
from decimal import Decimal
from common.functions.shkey import Shkey
import logging
import pandas as pd
import settings.models as sm


class UploadDupeView(generics.CreateAPIView):
    serializer_class = s.SingleFileSerializer

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data['file']
        date = request.data.get('date')

        try:
            dfh = DupeFileHandler()
            handler_response = dfh.handle_dupe_file(request, file, date)

            return Response(handler_response, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle general exceptions with a 500 Internal Server Error response
            print(str(e))
            return Response({'msg': {"type": "error", "body": "Internal Server Error"}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DupeFileHandler():
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error = None
        self.messages = []
        self.rings_updated = 0
        self.rings_created = 0
        # format YYYY-MM-DD
        self.dupe_file_date = ''
        self.dupe_shkey = ''

    def handle_dupe_file(self, request, f, date):
        # self.__init__() #  shouldnt be needed
        self.dupe_file_date = date
        self.dupe_shkey = Shkey.generate_shkey(date, 'd')
        print("reading the dupe")
        self.read_dupe(f)
        print("creating multifires")
        self.create_multifire_entries()
        print("finished")

        # All this is feedback msg to the user
        if self.error:
            handler_response = {'msg': {'type': 'error', 'body': self.error}}
        else:
            msg = ''
            if self.rings_created > 0:
                msg = f'{self.rings_created} rings created, '
            if self.rings_updated > 0:
                msg = msg + f'{self.rings_updated} rings updated'
            handler_response = {'msg': {'type': 'success', 'body': msg}}
        return handler_response

    def read_dupe(self, f):
        try:
            df = pd.read_csv(f, usecols=[
                "Inactive",
                "Level",
                "Drive",
                "Ring",
                "Number of Holes",
                "Metres Designed",
                "Draw Ratio",
                "Design Tonnes (100%)",
                "Drilling Complete Date",
                "Date Charge Completed",
                "FireBy",
                "Date Fired",
                "Shift Fired",
                "Status",
                "IsMFGroup",
                "Total Actual Tonnes",
                "BogComplete",
                "DesignCollarX",
                "DesignCollarY",
                "DesignCollarZ"])
        except ValueError as e:
            self.error = str(e)
            self.logger.error(f"Error: {e}")
            return
        # Replace all the 'nan' values for 'None'
        df2 = df.fillna("")

        try:
            with transaction.atomic():
                for _, row in df2.iterrows():
                    # this is for counting created or updated records
                    create_record = True
                    level = self.number_fix(row["Level"])
                    oredrive = row["Drive"]
                    ring_number_txt = row["Ring"]
                    status = self.status_adapter(row["Status"])

                    # Skip rings that should be deleted
                    if status != 'Complete':
                        alias = str(level) + "_" + oredrive + \
                            "_" + ring_number_txt

                        drill_shift = Shkey.generate_shkey(
                            row["Drilling Complete Date"])
                        charge_shift = Shkey.generate_shkey(
                            row["Date Charge Completed"])
                        shiftfired = Shkey.generate_shkey(
                            row["Date Fired"], row["Shift Fired"])
                        finished = Shkey.generate_shkey(row["BogComplete"])

                        if finished and shiftfired == '':
                            status = 'Abandoned'

                        draw_ratio = self.number_fix(row["Draw Ratio"])
                        in_flow = draw_ratio in [1, 1.08]

                        # Create a savepoint
                        sid = transaction.savepoint()

                        try:
                            # Try to get the existing record
                            existing_record = m.ProductionRing.objects.get(
                                level=level,
                                oredrive=oredrive,
                                ring_number_txt=ring_number_txt
                            )

                            # Update the existing record
                            existing_record.alias = alias
                            existing_record.is_active = not row["Inactive"]
                            existing_record.holes = self.number_fix(
                                row["Number of Holes"])
                            existing_record.drill_meters = self.number_fix(
                                row["Metres Designed"])
                            existing_record.draw_percentage = draw_ratio
                            existing_record.in_flow = in_flow
                            existing_record.designed_tonnes = self.number_fix(
                                row["Design Tonnes (100%)"])
                            existing_record.drill_complete_shift = drill_shift
                            existing_record.charge_shift = charge_shift
                            existing_record.fireby_date = self.reformat_date(
                                row["FireBy"])
                            existing_record.fired_shift = shiftfired
                            existing_record.status = status
                            existing_record.multi_fire_group = row["IsMFGroup"]
                            existing_record.bog_complete_shift = finished
                            existing_record.x = self.number_fix(
                                row["DesignCollarX"])
                            existing_record.y = self.number_fix(
                                row["DesignCollarY"])
                            existing_record.z = self.number_fix(
                                row["DesignCollarZ"])

                            if self.error:
                                transaction.savepoint_rollback(sid)
                                return
                            existing_record.save()
                            create_record = False

                        except m.ProductionRing.DoesNotExist:
                            # Create a new record
                            existing_record = m.ProductionRing.objects.create(
                                alias=alias,
                                is_active=not row["Inactive"],
                                level=level,
                                oredrive=oredrive,
                                ring_number_txt=ring_number_txt,
                                holes=self.number_fix(row["Number of Holes"]),
                                drill_meters=self.number_fix(
                                    row["Metres Designed"]),
                                draw_percentage=draw_ratio,
                                in_flow=in_flow,
                                designed_tonnes=self.number_fix(
                                    row["Design Tonnes (100%)"]),
                                drill_complete_shift=drill_shift,
                                charge_shift=charge_shift,
                                fireby_date=self.reformat_date(row["FireBy"]),
                                fired_shift=shiftfired,
                                status=status,
                                multi_fire_group=row["IsMFGroup"],
                                bog_complete_shift=finished,
                                x=self.number_fix(row["DesignCollarX"]),
                                y=self.number_fix(row["DesignCollarY"]),
                                z=self.number_fix(row["DesignCollarZ"])
                            )

                        if self.error:
                            transaction.savepoint_rollback(sid)
                            return

                        # Release the savepoint
                        transaction.savepoint_commit(sid)

                        tonnes = self.number_fix(row["Total Actual Tonnes"])

                        if tonnes > 0:
                            self.update_create_bog_tonnes(
                                tonnes, existing_record)

                        if create_record:
                            self.rings_created += 1
                        else:
                            self.rings_updated += 1

        except Exception as e:
            self.logger.error(f"Error: {e}")
            self.logger.error(f"Row causing the error: {row}")
            self.logger.exception("Traceback:")
            self.error = str(e)
            # Rollback to the savepoint (only the erroneous transaction)
            transaction.savepoint_rollback(sid)
            return

    def update_create_bog_tonnes(self, tonnes, existing_record):
        try:
            # Delete all existing linked BoggedTonnes records
            m.BoggedTonnes.objects.filter(
                production_ring=existing_record).delete()

            # Create a new BoggedTonnes record
            m.BoggedTonnes.objects.create(
                production_ring=existing_record,
                bogged_tonnes=tonnes,
                shkey=self.dupe_shkey,
                entered_by=None
            )
        except Exception as e:
            # Log or re-raise the exception for handling in the calling code
            self.logger.error(f"Error in update_create_bog_tonnes: {e}")
            raise e

    def status_adapter(self, status):
        status_mapping = {
            "MarkUp": "Designed",
            "Curr": "Bogging",
            "Comp": "Complete"
        }
        return status_mapping.get(status, status)

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

    def reformat_date(self, cell):
        if cell == '':
            return None
        if type(cell).__name__ == "NoneType" or type(cell).__name__ == "float" or len(cell) > 9 or len(cell) < 8:
            return None
        try:
            d = datetime.strptime(cell, "%d-%b-%y")
            formatted = d.strftime("%Y-%m-%d")
            return formatted

        except Exception as e:
            self.logger.error("reformat_date method error:", e, "cell:", cell)
            self.error = f"reformat_date error: {str(e)}"
            return None

    def reformat_datetime(self, cell):
        if len(cell) == 0:
            return ''
        try:
            # Create a timezone-aware datetime object in the GMT+10 timezone
            # 600 = 10 hours * 60 minutes/hour
            tz = timezone.get_fixed_timezone(600)
            dt = timezone.make_aware(datetime(cell.year, cell.month, cell.day,
                                              cell.hour, cell.minute, cell.second, cell.microsecond), tz)

            # Format the datetime object as a string
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S%z")

        except Exception as e:
            self.logger.error("error:", e, "cell:", cell)
            self.error = f"reformat_datetime error: {str(e)}"
            return

        return formatted

    def create_multifire_entries(self):
        mf = m.ProductionRing.objects.filter(is_active=True)
