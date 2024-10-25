from django.urls import path
from report.api.views.level_status import LevelStatusReportView
from report.api.views.orphaned_prod_rings import OrphanedProdRingsCountView

urlpatterns = [
    path('orphaned-prod-rings-count/', OrphanedProdRingsCountView.as_view(),
         name='orphaned-prod-rings-count'),
    path('prod/level-status/', LevelStatusReportView.as_view(), name='level-status'),
]
