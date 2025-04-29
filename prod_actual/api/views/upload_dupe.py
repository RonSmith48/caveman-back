from rest_framework import generics, status
from rest_framework.response import Response

import prod_actual.api.serializers as s
import prod_actual.models as m
import prod_concept.models as pcm
from prod_actual.api.views.ring_state import ConditionsAndStates

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
        self.load_ring_states()

        self.logger = logging.getLogger(__name__)
        self.error = None
        self.messages = []
        self.rings_updated = 0
        self.rings_created = 0
        # format YYYY-MM-DD
        self.dupe_file_date = ''
        self.dupe_shkey = ''

    def load_ring_states(self):
        cas = ConditionsAndStates()
        cas.ensure_mandatory_ring_states()
        self.ring_states = {
            state.pri_state: state
            for state in m.RingState.objects.filter(sec_state__isnull=True)
        }

    def handle_dupe_file(self, request, f, date):
        # self.__init__() #  shouldnt be needed
        self.dupe_file_date = date
        self.dupe_shkey = Shkey.generate_shkey(date, 'd')
        print("reading the dupe")
        self.read_dupe(f)
        # print("creating multifires")
        # self.create_multifire_entries()
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
                "Inactive", "Level", "Drive", "Ring", "Number of Holes", "Metres Designed",
                "Draw Ratio", "Design Tonnes (100%)", "Drilling Complete Date",
                "Date Charge Completed", "FireBy", "Date Fired", "Shift Fired", "Status",
                "IsMFGroup", "Total Actual Tonnes", "BogComplete",
                "DesignCollarX", "DesignCollarY", "DesignCollarZ"
            ])
        except ValueError as e:
            self.error = str(e)
            self.logger.error(f"Error reading CSV: {e}")
            return

        df2 = df.fillna("")

        missing = self.check_required_headers(df2)
        if missing:
            self.logger.error(f"Missing required columns: {missing}")
            return

        for _, row in df2.iterrows():
            try:
                with transaction.atomic():
                    self.process_row(row)
            except Exception as e:
                self.logger.error(f"Row failed: {e}")
                self.error = str(e)

        self.logger.info(
            f"Rings created: {self.rings_created}, updated: {self.rings_updated}")

    def check_required_headers(self, df):
        required = {
            "Inactive", "Level", "Drive", "Ring", "Number of Holes", "Metres Designed",
            "Draw Ratio", "Design Tonnes (100%)", "Drilling Complete Date",
            "Date Charge Completed", "FireBy", "Date Fired", "Shift Fired", "Status",
            "IsMFGroup", "Total Actual Tonnes", "BogComplete",
            "DesignCollarX", "DesignCollarY", "DesignCollarZ"
        }
        return required - set(df.columns)

    def process_row(self, row):

        level = self.number_fix(row["Level"])
        oredrive = row["Drive"]
        ring_number_txt = row["Ring"]
        status = self.status_adapter(row["Status"])

        if status == 'Complete':
            return  # Skip completed rings

        alias = f"{level}_{oredrive}_{ring_number_txt}"
        drill_shift = Shkey.generate_shkey(row["Drilling Complete Date"])
        charge_shift = Shkey.generate_shkey(row["Date Charge Completed"])
        shiftfired = Shkey.generate_shkey(
            row["Date Fired"], row["Shift Fired"])
        finished = Shkey.generate_shkey(row["BogComplete"])

        if finished and not shiftfired:
            status = 'Abandoned'

        holes = self.number_fix(row["Number of Holes"])
        drill_meters = self.number_fix(row["Metres Designed"])
        draw_ratio = self.number_fix(row["Draw Ratio"])
        designed_tonnes = self.number_fix(row["Design Tonnes (100%)"])
        tonnes = self.number_fix(row["Total Actual Tonnes"])
        x = self.number_fix(row["DesignCollarX"])
        y = self.number_fix(row["DesignCollarY"])
        z = self.number_fix(row["DesignCollarZ"])
        in_flow = draw_ratio in [1, 1.08]
        is_active = str(row["Inactive"]).strip(
        ).lower() not in ["true", "1", "yes"]

        try:
            ring, _ = m.ProductionRing.objects.update_or_create(
                level=level,
                oredrive=oredrive,
                ring_number_txt=ring_number_txt,
                defaults={
                    "alias": alias,
                    "prod_dev_code": "p",
                    "is_active": is_active,
                    "holes": holes,
                    "drill_meters": drill_meters,
                    "draw_percentage": draw_ratio,
                    "in_flow": in_flow,
                    "designed_tonnes": designed_tonnes,
                    "drill_complete_shift": drill_shift,
                    "charge_shift": charge_shift,
                    "fireby_date": self.reformat_date(row["FireBy"]),
                    "fired_shift": shiftfired,
                    "status": status,
                    "multi_fire_group": row["IsMFGroup"],
                    "bog_complete_shift": finished,
                    "x": x,
                    "y": y,
                    "z": z,
                }
            )

            # Create RingStateChange entries based on available data
            if drill_shift:
                self.status_drilled(ring, drill_shift, holes, drill_meters)

            if charge_shift:
                self.status_drilled(ring, drill_shift, holes, drill_meters)
                self.status_charged(ring, charge_shift)

            if shiftfired:
                self.status_drilled(ring, drill_shift, holes, drill_meters)
                self.status_charged(ring, charge_shift)
                self.status_fired(ring, shiftfired)

                
            if tonnes > 0:
                self.update_create_bog_tonnes(tonnes, ring)

            self.rings_created += 1  # Count all rows in this case

        except Exception as e:
            self.logger.error(f"Error processing row: {e}")
            self.logger.error(f"Row: {row}")
            self.logger.exception("Traceback:")
            self.error = str(e)
    
    def status_drilled(self, ring, drill_shift, holes, drill_meters):
        m.RingStateChange.objects.create(
            prod_ring=ring,
            state=self.ring_states.get('Drilled'),
            shkey=drill_shift,
            operation_complete=True,
            mtrs_drilled=drill_meters,
            holes_completed=holes,
        )
        
    def status_charged(self, ring, charge_shift):
        m.RingStateChange.objects.create(
            prod_ring=ring,
            state=self.ring_states.get('Charged'),
            shkey=charge_shift,
            operation_complete=True,
        )
        
    def status_fired(self, ring, shiftfired):
        m.RingStateChange.objects.create(
            prod_ring=ring,
            state=self.ring_states.get('Fired'),
            shkey=shiftfired,
            operation_complete=True,
        )
        # Record the bogging event in the following shift
        next_shift = Shkey.next_shkey(shiftfired)
        m.RingStateChange.objects.create(
            prod_ring=ring,
            state=self.ring_states.get('Bogging'),
            shkey=next_shift,
            operation_complete=False,
        )

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
            self.logger.error(f"reformat_date method error: {e}, cell: {cell}")
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
