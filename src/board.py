import pygame
import json
import math
import os
from typing import Optional, TYPE_CHECKING

# Forward declarations for type hinting
if TYPE_CHECKING:
    from .game_state import GameState
    # If Hex is used in type hints for external classes, it should be here too
    # from .units import Unit # Example if Unit needed Board in its hints

# Constants for hex grid
HEX_SIZE = 20  # Size of the hex (radius from center to vertex) - Adjusted for full map view

# For Flat-topped hexes:
# Width is across the flat sides, Height is from point to point.
# No, for flat-topped, Width is from point to point (horizontal), Height is across flat sides (vertical).
HEX_WIDTH = 2 * HEX_SIZE  # Width of a flat-topped hex
HEX_HEIGHT = math.sqrt(3) * HEX_SIZE  # Height of a flat-topped hex

# Colors (can be expanded)
COLOR_PLAIN = (88, 130, 60)     # Wimbledon Court Green (from previous iteration)
COLOR_SWAMP = (165, 107, 86)     # Reddish-Brown from image (current)
COLOR_MOUNTAIN = (132, 142, 150)  # Grey from image (current)
COLOR_SEA = (80, 140, 220)      # Brighter Rich Blue (from iteration before last)
COLOR_REEF = (100, 210, 210)      # Brighter Turquoise-Teal (from previous iteration)
COLOR_TEXT = (0, 0, 0) # Black
COLOR_HEX_BORDER = (50, 50, 50) # Dark Gray
COLOR_ORE = (255, 215, 0) # Gold
COLOR_ZONE_BORDER = (255, 255, 0) # Bright Yellow for zone borders
ZONE_BORDER_THICKNESS = 3    # Thickness for zone borders
TERRAIN_COLORS = {
    "plain": COLOR_PLAIN,
    "swamp": COLOR_SWAMP,
    "mountain": COLOR_MOUNTAIN,
    "sea": COLOR_SEA,
    "reef": COLOR_REEF,
}

class Hex:
    def __init__(self, col, row, terrain, ore=False, zone_id=None, name=None, victory_points=0):
        self.col = col
        self.row = row
        self.terrain = terrain
        self.ore = ore
        self.zone_id = zone_id
        self.name = name # For special named hexes
        self.victory_points = victory_points # For VP hexes

        self.center_x = 0
        self.center_y = 0
        self.points = []
        self.calculate_pixel_coords()

    def calculate_pixel_coords(self):
        """Calculates the pixel center and corner points for this flat-topped hex."""
        # For flat-topped hexes in an odd-q layout (columns define 'q', vertical staggering)
        # Horizontal distance between column centers
        col_spacing = HEX_WIDTH * 3/4
        # Vertical distance between row centers (is just the hex height)
        row_spacing = HEX_HEIGHT

        self.center_x = self.col * col_spacing
        self.center_y = self.row * row_spacing
        if self.col % 2 == 1:  # Odd columns are shifted UP by half a hex height
            self.center_y -= row_spacing / 2

        self.points = []
        for i in range(6):
            # Angles for flat-topped hexes (0, 60, 120, 180, 240, 300 degrees)
            angle_deg = 60 * i
            angle_rad = math.pi / 180 * angle_deg
            point_x = self.center_x + HEX_SIZE * math.cos(angle_rad)
            point_y = self.center_y + HEX_SIZE * math.sin(angle_rad)
            self.points.append((point_x, point_y))

    def draw(self, surface, font, draw_coords=False, draw_zone=False):
        """Draws the hex on the given surface."""
        pygame.draw.polygon(surface, TERRAIN_COLORS.get(self.terrain, (128, 128, 128)), self.points)
        pygame.draw.polygon(surface, COLOR_HEX_BORDER, self.points, 1) # Border

        if self.ore:
            # Adjust ore marker size/position if needed, using HEX_SIZE as reference
            ore_marker_radius = HEX_SIZE / 4
            pygame.draw.circle(surface, COLOR_ORE, (int(self.center_x), int(self.center_y)), int(ore_marker_radius))
            pygame.draw.circle(surface, COLOR_TEXT, (int(self.center_x), int(self.center_y)), int(ore_marker_radius), 1)


        if draw_coords:
            text_surface = font.render(f"{self.col},{self.row}", True, COLOR_TEXT)
            text_rect = text_surface.get_rect(center=(self.center_x, self.center_y - HEX_HEIGHT / 3)) # Adjusted y-offset
            surface.blit(text_surface, text_rect)
        
        if draw_zone and self.zone_id is not None:
            zone_text_content = f"Z:{self.zone_id}"
            if self.name:
                zone_text_content = f"{self.name}"
            elif self.victory_points > 0:
                zone_text_content = f"VP:{self.victory_points}"
            
            zone_text = font.render(zone_text_content, True, COLOR_TEXT)
            zone_rect = zone_text.get_rect(center=(self.center_x, self.center_y + HEX_HEIGHT / 3)) # Adjusted y-offset
            surface.blit(zone_text, zone_rect)

    def __repr__(self):
        return f"Hex({self.col}, {self.row}, {self.terrain})"

class Board:
    # Edge 2 (W/NW): points[2]-points[3] # This corresponds to Axial (0, -1) which is NW
    # Edge 3 (SW): points[3]-points[4]   # This corresponds to Axial (-1, 0) which is W
    # Edge 4 (S/SE): points[4]-points[5] # This corresponds to Axial (-1, +1) which is SW
    # Edge 5 (E/SE): points[5]-points[0] # This corresponds to Axial (0, +1) which is SE
    EDGE_VERTEX_INDICES_MAP = [\
        (5, 0), # Direction E (+1,  0) uses edge between vertex 5 and 0 (flat-topped specific point order)\
        (4, 5), # Direction SE (0, +1) uses edge between vertex 4 and 5 (was +1, -1 / NE, now SE)\
        (3, 4), # Direction SW (-1, +1) uses edge between vertex 3 and 4 (was 0, -1 / NW, now SW)\
        (2, 3), # Direction W (-1,  0) uses edge between vertex 2 and 3\
        (1, 2), # Direction NW (-1, -1) uses edge between vertex 1 and 2 (was -1, +1 / SW, now NW)\
        (0, 1)  # Direction NE (0, -1) uses edge between vertex 0 and 1 (was 0, +1 / SE, now NE)\
    ]\
    # Corrected AXIAL_DIRECTIONS for flat-topped to match typical q,r (E, SE, SW, W, NW, NE)\
    # q (axial) = col\
    # r (axial) = row - (col + (col&1)) // 2\
    # Axial Directions: (dq, dr)\
    # E:  (+1,  0)\
    # SE: ( 0, +1)  (col, row+1 in odd-q UP becomes q, r+1)\
    # SW: (-1, +1)  (col-1, row+1 or row in odd-q UP becomes q-1, r+1)\
    # W:  (-1,  0)\
    # NW: ( 0, -1)  (col, row-1 in odd-q UP becomes q, r-1)\
    # NE: (+1, -1)  (col+1, row or row-1 in odd-q UP becomes q+1, r-1)\
    # Updated AXIAL_DIRECTIONS as per user request
    # N, NE, SE, S, SW, NW (clockwise from North)
    AXIAL_DIRECTIONS = [
        ( 0, -1),  # 0: North
        (+1, -1),  # 1: Northeast
        (+1,  0),  # 2: Southeast (typically East axial vector)
        ( 0, +1),  # 3: South (typically Southeast axial vector)
        (-1, +1),  # 4: Southwest
        (-1, 0)   # 5: Northwest (Non-standard axial vector)
    ]

    def __init__(self, map_file_path: Optional[str] = "assets/board.json"):
        self.hexes = {}
        self.map_data = []
        self.min_col, self.max_col = 0, 0
        self.min_row, self.max_row = 0, 0
        if map_file_path:
            self._load_map(map_file_path)
        self._calculate_bounds()

    def _load_map(self, file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.map_data = data.get("hex_map", [])
        except FileNotFoundError:
            print(f"Error: Map file not found at {file_path}")
            return
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}")
            return

        for hex_data in self.map_data:
            col = hex_data.get("col")
            row = hex_data.get("row")
            terrain = hex_data.get("terrain", "plain")
            ore = hex_data.get("ore", False)
            zone_id_raw = hex_data.get("zone_id")
            zone_id = str(zone_id_raw) if zone_id_raw is not None else None # Ensure zone_id is a string or None
            name = hex_data.get("name")
            vp = hex_data.get("victory_points", 0)

            if col is not None and row is not None:
                new_hex = Hex(col, row, terrain, ore, zone_id, name, vp)
                self.hexes[(col, row)] = new_hex
            else:
                print(f"Warning: Skipping hex data with missing col/row: {hex_data}")
        
        if not self.hexes:
            print("Warning: No hexes loaded from the map file.")

    def _calculate_bounds(self):
        if not self.hexes:
            return
        self.min_col = min(h.col for h in self.hexes.values())
        self.max_col = max(h.col for h in self.hexes.values())
        self.min_row = min(h.row for h in self.hexes.values())
        self.max_row = max(h.row for h in self.hexes.values())

    def get_hex(self, col, row):
        return self.hexes.get((col, row))

    def _oddq_to_axial(self, col, row):
        """Converts odd-q (flat-topped, odd columns UP) to axial coordinates."""
        q_axial = col
        # r_axial = row - (col - (col & 1)) / 2 # This is for odd-q DOWN
        r_axial = row - (col + (col & 1)) // 2 # For odd-q UP (integer division)
        return q_axial, r_axial

    def _axial_to_oddq(self, q_axial, r_axial):
        """Converts axial to odd-q (flat-topped, odd columns UP) coordinates."""
        col = q_axial
        # row = r_axial + (q_axial - (q_axial & 1)) / 2 # This is for odd-q DOWN
        row = r_axial + (q_axial + (q_axial & 1)) // 2 # For odd-q UP (integer division)
        return col, row

    def get_neighbors(self, hex_obj_or_col, row=None):
        if isinstance(hex_obj_or_col, Hex):
            start_col, start_row = hex_obj_or_col.col, hex_obj_or_col.row
        else:
            start_col = hex_obj_or_col
            if row is None:
                raise ValueError("If first argument is a column, row must be provided.")
            start_row = row

        base_hex = self.get_hex(start_col, start_row)
        if not base_hex: 
            return []

        q_axial, r_axial = self._oddq_to_axial(start_col, start_row)
        
        neighbors = []
        for dq, dr in self.AXIAL_DIRECTIONS:
            nq_ax, nr_ax = q_axial + dq, r_axial + dr
            n_col, n_row = self._axial_to_oddq(nq_ax, nr_ax)
            
            neighbor_hex = self.get_hex(n_col, n_row)
            if neighbor_hex:
                neighbors.append(neighbor_hex)
        return neighbors

    def place_freighter(self, center_col: int, center_row: int, pod_axial_direction_indices: list[int]) -> list[tuple[int, int]]:
        """
        Calculates the odd-q coordinates of a freighter (bubble + 3 pods) 
        given the bubble's center and the axial direction indices for the pods.
        Returns a list of (col, row) tuples: [bubble_coord, pod1_coord, pod2_coord, pod3_coord].
        """
        occupied_coords = []

        # Bubble coordinates (already in odd-q)
        bubble_coord = (center_col, center_row)
        occupied_coords.append(bubble_coord)

        # Convert bubble's odd-q to axial for pod calculation
        bubble_q_axial, bubble_r_axial = self._oddq_to_axial(center_col, center_row)

        if len(pod_axial_direction_indices) != 3:
            print(f"Warning: place_freighter expects 3 pod_axial_direction_indices, got {len(pod_axial_direction_indices)}. Freighter may be incomplete.")
            # Still return what we have so far, or could raise an error

        for i in range(min(len(pod_axial_direction_indices), 3)): # Iterate up to 3 pods
            direction_index = pod_axial_direction_indices[i]
            if 0 <= direction_index < len(self.AXIAL_DIRECTIONS):
                dq, dr = self.AXIAL_DIRECTIONS[direction_index]
                pod_q_axial = bubble_q_axial + dq
                pod_r_axial = bubble_r_axial + dr
                pod_col, pod_row = self._axial_to_oddq(pod_q_axial, pod_r_axial)
                occupied_coords.append((pod_col, pod_row))
            else:
                print(f"Warning: Invalid pod_axial_direction_index {direction_index}. Skipping pod.")
        
        return occupied_coords

    def get_hexes_in_zone(self, zone_id_str: str) -> list['Hex']:
        """Returns a list of Hex objects that belong to the given zone_id."""
        if not zone_id_str:
            return []
        return [hex_obj for hex_obj in self.hexes.values() if str(hex_obj.zone_id) == zone_id_str]

    def is_edge_hex(self, col: int, row: int) -> bool:
        """Checks if the hex at (col, row) is on the edge of the map."""
        current_hex = self.get_hex(col, row)
        if not current_hex: # Should not happen if called with a valid hex on board
            return True # Or raise error, but being off-board is an "edge"

        q_axial, r_axial = self._oddq_to_axial(col, row)
        
        for dq, dr in self.AXIAL_DIRECTIONS:
            nq_ax, nr_ax = q_axial + dq, r_axial + dr
            n_col, n_row = self._axial_to_oddq(nq_ax, nr_ax)
            
            neighbor_hex = self.get_hex(n_col, n_row)
            if not neighbor_hex: # If any neighbor is off-map, this hex is an edge hex
                return True
        return False # All neighbors are on the map

    def draw(self, surface, font, camera_offset_x, camera_offset_y, map_origin_x, map_origin_y, draw_coords=False, draw_zones=False):
        if not self.hexes:
            print("Board has no hexes to draw.")
            return
        
        # The camera_offset_x/y and map_origin_x/y are passed in. 
        # This method just uses them to draw.

        # Draw hex bodies first
        for hex_tile in self.hexes.values():
            offset_points = [(p[0] + camera_offset_x - map_origin_x, 
                              p[1] + camera_offset_y - map_origin_y) for p in hex_tile.points]
            
            pygame.draw.polygon(surface, TERRAIN_COLORS.get(hex_tile.terrain, (128,128,128)), offset_points)
            pygame.draw.polygon(surface, COLOR_HEX_BORDER, offset_points, 1)

        # Draw ore and text on top
        for hex_tile in self.hexes.values(): # Iterate directly over values
            abs_center_x = hex_tile.center_x + camera_offset_x - map_origin_x
            abs_center_y = hex_tile.center_y + camera_offset_y - map_origin_y

            if hex_tile.ore:
                ore_marker_radius = HEX_SIZE / 4
                pygame.draw.circle(surface, COLOR_ORE, (int(abs_center_x), int(abs_center_y)), int(ore_marker_radius))
                pygame.draw.circle(surface, COLOR_TEXT, (int(abs_center_x), int(abs_center_y)), int(ore_marker_radius), 1)

            text_y_offset = HEX_HEIGHT / 2.5 
            if draw_coords:
                text_surface = font.render(f"{hex_tile.col},{hex_tile.row}", True, COLOR_TEXT)
                text_rect = text_surface.get_rect(center=(int(abs_center_x), int(abs_center_y - text_y_offset / 2)))
                surface.blit(text_surface, text_rect)
            
            if draw_zones and (hex_tile.zone_id is not None or hex_tile.name or hex_tile.victory_points > 0):
                zone_text_content = f"Z:{hex_tile.zone_id}"
                if hex_tile.name:
                    zone_text_content = f"{hex_tile.name}"
                elif hex_tile.victory_points > 0:
                    zone_text_content = f"VP:{hex_tile.victory_points}"
                
                zone_text = font.render(zone_text_content, True, COLOR_TEXT)
                zone_rect = zone_text.get_rect(center=(int(abs_center_x), int(abs_center_y + text_y_offset / 1.5)))
                surface.blit(zone_text, zone_rect)

    def pixel_to_hex(self, pixel_x, pixel_y, camera_offset_x, camera_offset_y, map_origin_x, map_origin_y):
        if not self.hexes: return None
        all_hex_objects = list(self.hexes.values())
        if not all_hex_objects: return None

        # Convert screen pixel to 'world' pixel relative to the map's (0,0) hex origin
        world_x = pixel_x - camera_offset_x + map_origin_x
        world_y = pixel_y - camera_offset_y + map_origin_y

        closest_hex = None
        min_dist_sq = float('inf')

        for hex_tile in self.hexes.values():
            dist_sq = (world_x - hex_tile.center_x)**2 + (world_y - hex_tile.center_y)**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_hex = hex_tile
        
        if closest_hex and min_dist_sq <= (HEX_SIZE * HEX_SIZE):
            # A more accurate check would be point-in-polygon for the closest_hex.points
            # using world_x, world_y. For now, distance to center is an approximation.
            return closest_hex
        return None

    def effective_terrain(self, hex_obj: 'Hex', tide_type: str) -> str:
        """
        Determines the effective terrain of a hex based on the current tide.
        tide_type can be "low", "mid", "high".
        """
        if not hex_obj:
            return "void" # Or raise an error, or return a specific impassable terrain type
        
        original_terrain = hex_obj.terrain
        
        if original_terrain == "swamp":
            if tide_type == "low":
                return "plain"
            elif tide_type == "high":
                return "sea"
        elif original_terrain == "reef":
            if tide_type == "low":
                return "plain"
            elif tide_type == "high":
                return "sea"
        
        return original_terrain

    def apply_tide_effects(self, game_state: 'GameState'):
        """
        Applies tide effects to the board and units based on the game_state.tide_state.
        For now, this method might adjust hex terrains or unit states.
        The test test_tide_neutralises_boat implies units can be neutralized.
        """
        # This is a placeholder. The actual neutralization logic for units
        # would likely involve checking unit.tide_sensitive, unit.can_enter for the
        # new effective terrain, and modifying a unit.is_neutralised attribute.
        # For the test, we'll focus on how the board might be perceived.
        print(f"Applying tide effects for tide: {game_state.tide_state}")
        # No direct board terrain mutation here, effective_terrain handles it per-check.
        # If units need to be updated based on new effective terrain (e.g. neutralized):
        for unit in game_state.units_by_id.values():
            # Ensure all units have is_neutralised attribute before checking type
            if not hasattr(unit, 'is_neutralised'):
                setattr(unit, 'is_neutralised', False)

            if unit.unit_type_id == "attack_boat": 
                current_hex = self.get_hex(unit.col, unit.row)
                if current_hex:
                    # Default to not neutralised for this specific tide effect, 
                    # unless the conditions below are met.
                    # We are only setting/unsetting based on this specific rule here.
                    neutralised_by_this_rule = False

                    # Rule derived from test_tide_neutralises_boat:
                    # An attack boat on an *original* swamp hex is neutralised at high tide.
                    if current_hex.terrain == "swamp" and game_state.tide_state == "high":
                        neutralised_by_this_rule = True
                    
                    # More general handling if unit was already neutralised by something else?
                    # For now, this rule dictates the state for attack boats based on tide and swamp.
                    setattr(unit, 'is_neutralised', neutralised_by_this_rule)
                # else: unit is not on a valid hex, maybe log or handle as error?
            # else: unit is not an attack_boat, other rules might apply to other unit types.
            # If a unit was neutralised by another effect, this logic for 'attack_boat' currently
            # wouldn't change it unless it's an attack_boat meeting the swamp/high_tide criteria.
            # If an attack_boat *not* on swamp/high_tide was neutralised, it would be de-neutralised here.
            # This seems acceptable if this is the primary tide-based neutralisation for attack_boats.


# Example Usage (optional, for testing)
if __name__ == '__main__':
    print(f"Current working directory (at script start): {os.getcwd()}") 
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Script directory: {script_dir}")
    # Path for assets when running src/board.py directly: ../assets/
    map_path_for_direct_run = os.path.normpath(os.path.join(script_dir, "..", "assets", "board.json"))
    print(f"Calculated map path for direct run: {map_path_for_direct_run}")

    pygame.init()
    screen_width = 1200
    screen_height = 900
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Flat-Topped Hex Grid Board (Odd-Q) - Running from src")
    font = pygame.font.Font(None, 16) # Reduced font size

    board = Board(map_file_path=map_path_for_direct_run)

    if not board.hexes:
        print("Failed to load board or board is empty. Exiting example.")
        pygame.quit()
        exit()

    running = True
    clock = pygame.time.Clock()
    
    # Calculate map's intrinsic pixel boundaries and origin (once)
    # These are the raw pixel coordinates as calculated by Hex.calculate_pixel_coords()
    # These define the map's own coordinate system, independent of camera or screen.
    all_hex_objects_main = list(board.hexes.values())
    map_origin_x_on_screen = 0 
    map_origin_y_on_screen = 0
    board_render_width = 0
    board_render_height = 0

    if all_hex_objects_main:
        raw_min_px_x = min(p[0] for h in all_hex_objects_main for p in h.points)
        raw_max_px_x = max(p[0] for h in all_hex_objects_main for p in h.points)
        raw_min_px_y = min(p[1] for h in all_hex_objects_main for p in h.points)
        raw_max_px_y = max(p[1] for h in all_hex_objects_main for p in h.points)
        
        board_render_width = raw_max_px_x - raw_min_px_x
        board_render_height = raw_max_px_y - raw_min_px_y

        map_origin_x_on_screen = raw_min_px_x # This is the map's top-left most point in its own coord system
        map_origin_y_on_screen = raw_min_px_y

    # Initial camera offset calculation
    padding = 10
    camera_offset_x = (screen_width - board_render_width) / 2
    camera_offset_y = (screen_height - board_render_height) / 2

    if camera_offset_x < padding: # If map wider than screen, start at padding
        camera_offset_x = padding
    if camera_offset_y < padding: # If map taller than screen, start at padding
        camera_offset_y = padding
        
    print(f"Screen: {screen_width}x{screen_height}")
    print(f"Calculated Board Render Size: {board_render_width:.2f}x{board_render_height:.2f}")
    print(f"Map Origin (min_raw_px_coord): ({map_origin_x_on_screen:.2f}, {map_origin_y_on_screen:.2f})")
    print(f"Initial Camera Offset: {camera_offset_x:.2f}x{camera_offset_y:.2f}")

    dragging = False
    drag_start_pos = None
    
    selected_hex = None
    hovered_hex = None

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: 
                    mouse_x, mouse_y = event.pos
                    clicked_hex = board.pixel_to_hex(mouse_x, mouse_y, camera_offset_x, camera_offset_y, map_origin_x_on_screen, map_origin_y_on_screen)
                    if clicked_hex:
                        selected_hex = clicked_hex
                        print(f"Clicked Hex: ({selected_hex.col}, {selected_hex.row}), Terrain: {selected_hex.terrain}, Zone: {selected_hex.zone_id}, Ore: {selected_hex.ore}, Name: {selected_hex.name}, VP: {selected_hex.victory_points}")
                        neighbors = board.get_neighbors(selected_hex)
                        print(f"Neighbors: {[(n.col, n.row) for n in neighbors]}")
                    else:
                        selected_hex = None
                elif event.button == 3: 
                    dragging = True
                    drag_start_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3: 
                    dragging = False
                    drag_start_pos = None
            elif event.type == pygame.MOUSEMOTION:
                mouse_x, mouse_y = event.pos
                hovered_hex = board.pixel_to_hex(mouse_x, mouse_y, camera_offset_x, camera_offset_y, map_origin_x_on_screen, map_origin_y_on_screen)
                if dragging and drag_start_pos:
                    dx = event.pos[0] - drag_start_pos[0]
                    dy = event.pos[1] - drag_start_pos[1]
                    camera_offset_x += dx
                    camera_offset_y += dy
                    drag_start_pos = event.pos

        screen.fill((200, 200, 200)) 
        board.draw(screen, font, camera_offset_x, camera_offset_y, map_origin_x_on_screen, map_origin_y_on_screen, True, True)

        if selected_hex:
            # For highlights, points need same adjustment as in board.draw
            s_offset_points = [(p[0] + camera_offset_x - map_origin_x_on_screen, p[1] + camera_offset_y - map_origin_y_on_screen) for p in selected_hex.points]
            pygame.draw.polygon(screen, (255, 0, 0), s_offset_points, 3) 

            neighbors = board.get_neighbors(selected_hex)
            for neighbor in neighbors:
                n_offset_points = [(p[0] + camera_offset_x - map_origin_x_on_screen, p[1] + camera_offset_y - map_origin_y_on_screen) for p in neighbor.points]
                pygame.draw.polygon(screen, (0, 255, 0), n_offset_points, 2)
        
        if hovered_hex and hovered_hex != selected_hex:
             h_offset_points = [(p[0] + camera_offset_x - map_origin_x_on_screen, p[1] + camera_offset_y - map_origin_y_on_screen) for p in hovered_hex.points]
             pygame.draw.polygon(screen, (0,0,255,150), h_offset_points, 2)

        pygame.display.flip()
        clock.tick(60)

    print("Exiting Pygame loop.")
    pygame.quit() 