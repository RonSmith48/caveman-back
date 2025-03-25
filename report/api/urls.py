from django.urls import path
from report.api.views.level_status import LevelStatusReportView, LevelStatusCreateReportView
from report.api.views.orphaned_prod_rings import OrphanedProdRingsCountView

import report.api.views.geology as g
import report.api.views.production as p

urlpatterns = [
    path('geo/fired-ring-grade/', g.FiredRingGradeView.as_view(), name='geo-fired'),
    path('orphaned-prod-rings-count/', OrphanedProdRingsCountView.as_view(),
         name='orphaned-prod-rings-count'),
    path('prod/bog-verify/', p.BogVerifyReportView.as_view(), name='bog-verify'),
    path('prod/dcf/', p.DCFReportView.as_view(), name='dcf'),
    path('prod/level-status/', LevelStatusReportView.as_view(), name='level-status'),
    path('prod/level-status/create/',
         LevelStatusCreateReportView.as_view(), name='level-status-create'),
]
