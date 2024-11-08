from rest_framework import generics
import prod_concept.models as m
import prod_concept.api.serializers as s

import math


class BlockAdjacencyFunctions():
    def __init__(self) -> None:
        self.opposite_direction = {'N': 'S', 'NE': 'SW', 'E': 'W',
                                   'SE': 'NW', 'S': 'N', 'SW': 'NE', 'W': 'E', 'NW': 'SE'}
        self.dir_tolerance = {
            'N': ['NW', 'N', 'NE'],
            'NE': ['N', 'NE', 'E'],
            'E': ['NE', 'E', 'SE'],
            'SE': ['E', 'SE', 'S'],
            'S': ['SE', 'S', 'SW'],
            'SW': ['S', 'SW', 'W'],
            'W': ['SW', 'W', 'NW'],
            'NW': ['W', 'NW', 'N']
        }
        self.search_radius = 20

    def remap_mine(self):
        levels_list = m.FlowModelConceptRing.objects.filter(
            is_active=True).values_list('level', flat=True).distinct()
        self.remap_levels(levels_list)

    def remap_levels(self, levels_list):
        # prod_concept/.. upload_concept.py calls this method after upload
        for level in levels_list:
            self.remap_level(level)

    def remap_level(self, level):
        self.remove_links_on_level(level)
        blocks = m.FlowModelConceptRing.objects.filter(
            is_active=True, level=level)
        for block in blocks:
            adjacent_blocks = self.find_adjacent_blocks(block, blocks)
            self.create_links(block, adjacent_blocks)

    def remove_links_on_level(self, level):
        # Step 1: Identify all blocks on the level to be remapped (e.g., level 3)
        blocks_on_level = m.FlowModelConceptRing.objects.filter(level=level)

        # Step 2: Remove adjacencies where the block is on the remapped level
        m.BlockAdjacency.objects.filter(block__in=blocks_on_level).delete()

        # Step 3: Remove adjacencies where the adjacent block is on the remapped level
        m.BlockAdjacency.objects.filter(
            adjacent_block__in=blocks_on_level).delete()

    def find_adjacent_blocks(self, block, blocks):
        direction = {'N': {}, 'NE': {}, 'E': {}, 'SE': {},
                     'S': {}, 'SW': {}, 'W': {}, 'NW': {}}

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
        distance = ((float(this_block.x) - float(that_block.x)) **
                    2 + (float(this_block.y) - float(that_block.y)) ** 2) ** 0.5
        return distance

    def create_links(self, block, adjacent_blocks):
        for bearing, data in adjacent_blocks.items():
            if data:  # Check if there's an adjacent block stored in this direction
                m.BlockAdjacency.objects.create(
                    block=block,
                    adjacent_block=data['block'],
                    direction=bearing
                )

    def get_opposite_direction(self, direction):
        return self.opposite_direction[direction]

    def find_first_block(self, concept_desc, mining_direction):
        """
        Finds the block with the greatest distance in the opposite direction of the specified mining direction.

        :param concept_desc: Drive name in Deswik.
        :param mining_direction: Mining direction (e.g., 'N', 'NE').
        :return: The block with the greatest distance in the opposite direction of mining.
        """
        blocks = m.FlowModelConceptRing.objects.filter(
            is_active=True, description=concept_desc)

        if not blocks.exists():
            return None

        reference_block = blocks.first()

        opposite_direction = self.get_opposite_direction(mining_direction)

        farthest_block = None
        max_distance = 0

        for block in blocks:
            if block != reference_block:

                direction = self.determine_direction(reference_block, block)

                if direction == opposite_direction:
                    distance = self.get_dist_to_block(reference_block, block)
                    if distance > max_distance:
                        max_distance = distance
                        farthest_block = block

        return farthest_block
    
    def step_next_block(self, this_block, mining_direction):
        '''
        Takes a step in the mining_direction.
        Will check general direction for blocks in the same drive
        Returns next block or None.
        '''
        this_block_desc = this_block.description
        tolerated_directions = self.dir_tolerance.get(mining_direction, [])

        # Check for adjacent blocks matching the direction tolerances
        next_block_adjacency = m.BlockAdjacency.objects.filter(
            block=this_block,
            direction__in=tolerated_directions  # Tolerated directions
        ).select_related('adjacent_block')

        for adjacency in next_block_adjacency:
            # Ensure the adjacent block's description matches the current block's drive
            if adjacency.adjacent_block.description == this_block_desc:
                return adjacency.adjacent_block

        return None

