from django.urls import path
from prod_actual.api.views.crud import ProdRingListCreateView, ProdRingRetrieveUpdateDestroyView, ProdRingStatusListView
from prod_actual.api.views.ring_editor import LevelListView, OredriveListView, RingNumberListView
from prod_actual.api.views.upload_dupe import UploadDupeView
from prod_actual.api.views.location_history import LocationHistoryView
from prod_actual.api.views.ring_state import RingStateListView, RingStateDeleteView
from prod_actual.api.views.geology import OverdrawRingView
import prod_actual.api.views.drill_blast as db
import prod_actual.api.views.bdcf as bdcf
import common.api.views as v

urlpatterns = [
    path('export/tables/', v.ExportableTablesView.as_view(), name='export-tables'),
    path('import/', bdcf.BoggingRingsView.as_view(), name='bdcf-bog'),
]
