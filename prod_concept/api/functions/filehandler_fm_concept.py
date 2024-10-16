from django.db import transaction
from django.contrib.auth import get_user_model
import logging
import pandas as pd
import prod_concept.models as m

User = get_user_model()
logger = logging.getLogger('custom_logger')


class ConceptRingsFileHandler(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rings_created = 0
        self.rings_updated = 0
        self.error_msg = None
        self.success_msg = None
        self.user = ''

    def handle_flow_concept_file(self, request, file):
        self.user = request.user
        self.read_flow_concept_file(file)
        if self.error_msg:
            return {'msg': {'type': 'error', 'body': self.error_msg}}
        else:
            self.success_msg = f'{self.rings_created} conceptual rings created, {
                self.rings_updated} updated'

            logger.user_activity("flow model update", extra={
                'user': request.user,
                'url': request.build_absolute_uri(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'description': f'{request.user.full_name} uploaded a flow model update. {self.rings_created} conceptual rings created, {self.rings_updated} updated',
            })
            return {'msg': {'type': 'success', 'body': self.success_msg}}

    def read_flow_concept_file(self, file):
        required_columns = [
            "ID",
            "LEVEL",
            "HEADING",
            "DRIVE",
            "Name",
            "LOC",
            "X",
            "Y",
            "Z",
            "PGCA_Modelled Tonnes",
            "DRAW_ZONE",
            "Density",
            "PGCA_Modelled Au",
            "PGCA_Modelled Cu"]
        try:
            df = pd.read_csv(file, usecols=required_columns)
        except ValueError as e:
            df_check = pd.read_csv(file)
            missing_columns = [
                col for col in required_columns if col not in df_check.columns]

            if missing_columns:
                error_msg = f"Missing columns in the file: {
                    ', '.join(missing_columns)}"
                logger.warning("flow model update failure", exc_info=True, extra={
                    'user': self.user,
                    'additional_info': error_msg,
                })
            else:
                logger.error("CSV file read error", exc_info=True, extra={
                    'user': self.user,
                    'stack_trace': e,
                    'additional_info': 'A CSV file read error other than missing columns',
                })
                error_msg = 'There was error in the CSV file'
            return
        # Replace all the 'nan' values for 'None'
        df2 = df.fillna("")

        try:
            with transaction.atomic():
                for _, row in df2.iterrows():
                    # Initialize flag to track if a record is created or updated
                    create_record = True

                    try:
                        drv_num = int(row["DRIVE"])
                    except ValueError:
                        # Ignore rows without a valid DRIVE number
                        continue

                    bs_id = row["ID"]

                    # Create a savepoint
                    sid = transaction.savepoint()

                    try:
                        # Attempt to get the existing record
                        existing_record = m.FlowModelConceptRing.objects.get(
                            blastsolids_id=bs_id)

                        # Update the existing record
                        self.update_existing_record(existing_record, row)
                        create_record = False
                    except m.FlowModelConceptRing.DoesNotExist:
                        # Create a new record if it does not exist
                        self.create_new_record(row)

                    if self.error_msg:
                        # If an error was encountered in helper methods, rollback and return
                        transaction.savepoint_rollback(sid)
                        return

                    # Commit the savepoint if no errors occurred
                    transaction.savepoint_commit(sid)

                    # Update counters
                    if create_record:
                        self.rings_created += 1
                    else:
                        self.rings_updated += 1

        except Exception as e:
            logger.warning("flow model file data error", exc_info=True, extra={
                'user': self.user,
                'additional_info': e,
            })
            self.error_msg = "flow model file data error"
            # Rollback to the savepoint (only the erroneous transaction)
            transaction.savepoint_rollback(sid)
            return

    def update_existing_record(self, record, row):
        """Helper method to update an existing record."""
        record.description = row["Name"]
        record.inactive = False
        record.level = self.number_fix(row["LEVEL"])
        record.heading = row["HEADING"]
        record.drive = self.number_fix(row["DRIVE"])
        record.loc = row["LOC"]
        record.x = self.number_fix(row["X"])
        record.y = self.number_fix(row["Y"])
        record.z = self.number_fix(row["Z"])
        record.pgca_modelled_tonnes = self.number_fix(
            row["PGCA_Modelled Tonnes"])
        record.draw_zone = self.number_fix(row["DRAW_ZONE"])
        record.density = self.number_fix(row["Density"])
        record.modelled_au = self.number_fix(row["PGCA_Modelled Au"])
        record.modelled_cu = self.number_fix(row["PGCA_Modelled Cu"])

        if self.error_msg:
            return

        record.save()

    def create_new_record(self, row):
        """Helper method to create a new record."""
        m.FlowModelConceptRing.objects.create(
            description=row["Name"],
            inactive=False,
            level=self.number_fix(row["LEVEL"]),
            blastsolids_id=row["ID"],
            heading=row["HEADING"],
            drive=self.number_fix(row["DRIVE"]),
            loc=row["LOC"],
            x=self.number_fix(row["X"]),
            y=self.number_fix(row["Y"]),
            z=self.number_fix(row["Z"]),
            pgca_modelled_tonnes=self.number_fix(row["PGCA_Modelled Tonnes"]),
            draw_zone=self.number_fix(row["DRAW_ZONE"]),
            density=self.number_fix(row["Density"]),
            modelled_au=self.number_fix(row["PGCA_Modelled Au"]),
            modelled_cu=self.number_fix(row["PGCA_Modelled Cu"])
        )

    def number_fix(self, cell):
        """
        Convert the input to a float if possible. Handles strings that represent numbers
        and returns 0 for non-numeric strings. If the input is already numeric or None, 
        it returns the input as is.
        """
        if cell is None:
            return 0

        if isinstance(cell, (int, float)):
            return cell

        if isinstance(cell, str):
            cell = cell.strip()
            try:
                return float(cell)
            except ValueError:
                self.logger.warning(
                    f"Non-numeric string encountered: '{cell}'")
                self.error_msg = f"Non-numeric string encountered: {cell}"
                return 0

        # If the input is of an unexpected type, return 0 or consider raising an exception
        self.logger.warning(f"Unexpected type encountered: {type(cell)}")
        self.error_msg = f"Unexpected type encountered: {type(cell)}"
        return 0
