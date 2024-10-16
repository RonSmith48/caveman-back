import logging
from django.http import JsonResponse
from django.db import connections


class Pitram(object):

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def pitram_query_json(self, query_string, params=None):
        with connections['pitram'].cursor() as cursor:
            cursor.execute(query_string)
            results = cursor.fetchall()

        # You can convert them to a list of dictionaries or any desired format
        data = [dict(zip([column[0] for column in cursor.description], row))
                for row in results]

        # Return the data as JSON
        return JsonResponse(data, safe=False)

    def pitram_query_rs(self, query_string, params=None):
        with connections['pitram'].cursor() as cursor:
            cursor.execute(query_string, params)
            results = cursor.fetchall()

        return results
