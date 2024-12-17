from django.urls import path
from prod_actual.api.views.crud import ProdRingListCreateView, ProdRingRetrieveUpdateDestroyView, ProdRingStatusListView
from prod_actual.api.views.ring_inspector import LevelListView, OredriveListView, RingNumberListView, RingView
from prod_actual.api.views.upload_dupe import UploadDupeView
from prod_actual.api.views.prod_orphans import OrphanListView, MatchProdConceptRingsView
import prod_actual.api.views.bdcf as bdcf

urlpatterns = [
    path('bdcf/bog/', bdcf.BoggingRingsView.as_view(), name='bdcf-bog'),
    path('bdcf/bog/<int:location_id>/',
         bdcf.BoggingMovementsView.as_view(), name='bdcf-bog'),
    path('bdcf/conditions/<str:stat>/',
         bdcf.ConditionsListView.as_view(), name='bdcf-conditions'),
    path('bdcf/drill/', bdcf.DrillEntryView.as_view(), name='bdcf-drill'),
    path('bdcf/drilled/<str:lvl_od>/',
         bdcf.DrillEntryRingsListView.as_view(), name='bdcf-drill'),
    path('bdcf/charge/', bdcf.ChargeEntryView.as_view(), name='bdcf-charge'),
    path('bdcf/charge/<str:lvl_od>/',
         bdcf.ChargeEntryRingsListView.as_view(), name='bdcf-charge'),
    path('bdcf/fire/', bdcf.FireEntryView.as_view(), name='bdcf-fire'),
    path('orphaned-rings/', OrphanListView.as_view(), name='prod-orphans'),
    path('orphaned-rings/process/',
         MatchProdConceptRingsView.as_view(), name='process-orphans'),
    path('prod-rings/', ProdRingListCreateView.as_view(),
         name='prod-ring-list-create'),
    path('prod-rings/<int:pk>/',
         ProdRingRetrieveUpdateDestroyView.as_view(), name='prod-ring-detail'),
    path('prod-rings/status/<str:status>/',
         ProdRingStatusListView.as_view(), name='prod-ring-status-list'),
    path('ring-inspector/levels/', LevelListView.as_view(), name='level-list'),
    path('ring-inspector/<int:level>/',
         OredriveListView.as_view(), name='oredrive-list'),
    path('ring-inspector/<int:level>/<str:oredrive>/',
         RingNumberListView.as_view(), name='ring-number-list'),
    path('ring-inspector/<int:level>/<str:oredrive>/<str:ring_number_txt>/',
         RingView.as_view(), name='ring-view'),
    path('upload/dupe/', UploadDupeView.as_view(), name='upload-dupe'),
]
