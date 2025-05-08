from django.urls import path
from report.api.views.level_status import LevelStatusReportView, LevelStatusCreateReportView

import report.api.views.geology as g
import report.api.views.production as p
import report.api.views.location_history as lh

urlpatterns = [
    path('geo/fired-ring-grade/', g.FiredRingGradeView.as_view(), name='geo-fired'),
    path('location-history/<int:location_id>/',
         lh.LocationHistoryView.as_view(), name='location-history'),
    path('prod/bog-verify/', p.BogVerifyReportView.as_view(), name='bog-verify'),
    path('prod/dcf/', p.DCFReportView.as_view(), name='dcf'),
    path('prod/dupe/', p.DataDupeView.as_view(), name='dupe'),
    path('prod/level-status/', LevelStatusReportView.as_view(), name='level-status'),
    path('prod/level-status/create/',
         LevelStatusCreateReportView.as_view(), name='level-status-create'),
]
