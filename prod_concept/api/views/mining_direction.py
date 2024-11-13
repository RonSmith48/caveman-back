from rest_framework import generics, status
from rest_framework.response import Response

import prod_concept.models as m
import prod_actual.models as pam

from common.functions.status import Status
from common.functions.block_adjacency import BlockAdjacencyFunctions
from settings.models import ProjectSetting


class MiningDirectionView(generics.ListAPIView):
    def __init__(self):
        self.opposite_direction = {'N': 'S', 'NE': 'SW', 'E': 'W',
                                   'SE': 'NW', 'S': 'N', 'SW': 'NE', 'W': 'E', 'NW': 'SE'}

    def get(self, request, *args, **kwargs):

 
        return Response({'msg': {"type": "error", "body": "Internal Server Error"}}, status=status.HTTP_501_NOT_IMPLEMENTED)
        

    def update_mining_direction(self):
        baf = BlockAdjacencyFunctions()
        drives = m.FlowModelConceptRing.objects.values_list('description', flat=True).distinct()

        for drive in drives:
            blocks_in_drive = m.FlowModelConceptRing.objects.filter(description=drive)
            if blocks_in_drive:
                ref_block = blocks_in_drive.first()
                if ref_block:
                    last = baf.get_farthest_block(ref_block, blocks_in_drive)
                    if last:
                        first = baf.get_farthest_block(last, blocks_in_drive)
                        if first:
                            mining_direction = baf.determine_direction(first, last)
                            if mining_direction:

                                m.MiningDirection.objects.create(
                                    description = drive,
                                    mining_direction = mining_direction,
                                    first_block = first,
                                    last_block = last,
                                )
                            else:
                                print("no mining dir", drive)
                        else:
                            print("no first", drive)
                    else:
                        print("no last", drive)
                else:
                    print("no ref block", drive)
            else:
                print("no blocks in drive", drive)
                            
        print("finished")