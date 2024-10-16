from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from report.models import JsonReport

from prod_actual.api.views.prod_orphans import ProdOrphans


class OrphanedProdRingsCountView(APIView):
    def get(self, request):
        report_name = 'orphaned prod rings count'

        try:
            report = JsonReport.objects.get(name=report_name)
            return Response(report.report, status=status.HTTP_200_OK)
        except JsonReport.DoesNotExist:
            po = ProdOrphans()
            orphans = po.store_orphan_count()
            return Response(orphans, status=status.HTTP_200_OK)
