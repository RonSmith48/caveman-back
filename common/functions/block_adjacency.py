from rest_framework import generics
import prod_concept.models as m
import prod_concept.api.serializers as s

import math

class BlockAdjacency():
    def __init__(self) -> None:
        self.search_radius = 20

    def remap_level(self, level):
        self.remove_links_on_level(level)
        blocks = m.FlowModelConceptRing.objects.filter(is_active=True, level=level)
        for block in blocks:
            adjacent_blocks = self.find_adjacent_blocks(block, blocks)
            self.create_links(block, adjacent_blocks)
            

    def remove_links_on_level(self, level):
        # Step 1: Identify all blocks on the level to be remapped (e.g., level 3)
        blocks_on_level = m.FlowModelConceptRing.objects.filter(level=level)

        # Step 2: Remove adjacencies where the block is on the remapped level
        m.BlockAdjacency.objects.filter(block__in=blocks_on_level).delete()

        # Step 3: Remove adjacencies where the adjacent block is on the remapped level
        m.BlockAdjacency.objects.filter(adjacent_block__in=blocks_on_level).delete()

    def find_adjacent_blocks(self, block, blocks):
        direction = {'N': {}, 'NE': {}, 'E': {}, 'SE': {}, 'S': {}, 'SW': {}, 'W': {}, 'NW': {}}

        for b in blocks:
            if b.blastsolids_id != block.blastsolids_id:
                if self.is_adjacent(block, b):
                    dist = self.get_dist_to_block(block, b)
                    
                    if dist < self.search_radius:
                        bearing = self.determine_direction(block, b)
                        
                        # If there's no block for the current bearing or the new block is closer
                        if not direction[bearing] or dist < direction[bearing]['distance']:
                            direction[bearing] = {'block': b, 'distance': dist}
        
        return direction


    def determine_direction(self, this_block, that_block):
        # Calculate the differences in x and y coordinates
        dx = that_block.x - this_block.x
        dy = that_block.y - this_block.y
        
        # Calculate the angle in radians and convert to degrees
        angle = math.degrees(math.atan2(dy, dx))
        
        # Normalize the angle to a 0-360 degree range
        angle = (angle + 360) % 360

        # Determine the direction based on the angle
        if 337.5 <= angle < 360 or 0 <= angle < 22.5:
            return 'E'
        elif 22.5 <= angle < 67.5:
            return 'NE'
        elif 67.5 <= angle < 112.5:
            return 'N'
        elif 112.5 <= angle < 157.5:
            return 'NW'
        elif 157.5 <= angle < 202.5:
            return 'W'
        elif 202.5 <= angle < 247.5:
            return 'SW'
        elif 247.5 <= angle < 292.5:
            return 'S'
        elif 292.5 <= angle < 337.5:
            return 'SE'

        

    def is_adjacent(self, this_block, that_block):
        if abs(this_block.x - that_block.x) > self.search_radius:
            return False
        elif abs(this_block.y - that_block.y) > self.search_radius:
            return False
        else:
            return True


    def get_dist_to_block(self, this_block, that_block):
        # Convert x and y coordinates to floats before doing the distance calculation
        distance = ((float(this_block.x) - float(that_block.x)) ** 2 + (float(this_block.y) - float(that_block.y)) ** 2) ** 0.5
        return distance
    
    def create_links(self, block, adjacent_blocks):
        for bearing, data in adjacent_blocks.items():
            if data:  # Check if there's an adjacent block stored in this direction
                m.BlockAdjacency.objects.create(
                    block=block,
                    adjacent_block=data['block'],
                    direction=bearing
                )

