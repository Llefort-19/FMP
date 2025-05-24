import json
import os
import random
import math
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon, Patch, Circle
from matplotlib.lines import Line2D
from typing import List, Dict, Any, Optional, Tuple, Set
import uuid # Add uuid for unique unit IDs

from board import (
    Board, 
    HEX_SIZE as BOARD_HEX_SIZE, 
    TERRAIN_COLORS as BOARD_TERRAIN_COLORS, 
    COLOR_ORE as BOARD_COLOR_ORE,
    COLOR_HEX_BORDER as BOARD_COLOR_HEX_BORDER,
    COLOR_TEXT as BOARD_COLOR_TEXT
)
from units import UnitType, Unit
from tides import TideDeck
from turn_manager import TurnManager, TurnDefinition
from player import Player

# Define the asset path relative to the current file's location
ASSET_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))

# Helper to convert RGB tuple to hex string for matplotlib
def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

class GameEngine:
    def __init__(self, num_players: int = 2):
        """Initialize the game engine with the specified number of players."""
        # Load game data (excluding board_data, handled by Board class)
        self.tide_cards_data = self._load_json_data("tide cards.json")
        self.unit_data = self._load_json_data("unit.json")
        self.turns_data = self._load_json_data("turns.json")

        # Initialize game components
        board_map_path = os.path.join(ASSET_PATH, "board.json")
        self.board = Board(map_file_path=board_map_path) # Board now loads its own data
        
        self.tide_deck = TideDeck(self.tide_cards_data) if self.tide_cards_data else None
        self.turn_manager = TurnManager(self.turns_data) if self.turns_data else None
        
        # Initialize unit types
        self.unit_types: Dict[str, UnitType] = {}
        if self.unit_data:
            raw_unit_list = self.unit_data.get('units', [])
            for unit_dict in raw_unit_list:
                if 'id' not in unit_dict:
                    print(f"Warning: Unit data missing 'id': {unit_dict}. Skipping.")
                    continue
                try:
                    unit_type_obj = UnitType.from_dict(unit_dict)
                    self.unit_types[unit_type_obj.id] = unit_type_obj
                except Exception as e:
                    print(f"Error processing unit data for ID '{unit_dict.get('id')}': {e}")

        # Debug print Starfreighter pod shapes
        if 'starfreighter' in self.unit_types:
            sf_type = self.unit_types['starfreighter']
            if sf_type.pod_shapes:
                print(f"DEBUG ENGINE INIT: Starfreighter Pod Shape 0: {sf_type.pod_shapes[0].pod_angles}")
                print(f"DEBUG ENGINE INIT: Starfreighter Pod Shape 1: {sf_type.pod_shapes[1].pod_angles}")
            else:
                print("DEBUG ENGINE INIT: Starfreighter has no pod_shapes loaded.")

        # Initialize player-related attributes
        self.players: List[Player] = []
        self.current_player_index: int = 0
        self._setup_players(num_players)
        
        # Freighter landing tracking
        self.freighter_landings: Dict[str, Dict[str, Any]] = {} # Stores info about each player's landed freighter
        self.landed_freighter_zones: Set[str] = set() # Stores zone_ids where freighters have landed
        
        # Game state
        self.game_over: bool = False
        
        print(f"GameEngine initialized for {num_players} players.")

    def _load_json_data(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load JSON data from a file in the ASSET_PATH directory."""
        filepath: str = os.path.join(ASSET_PATH, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data: Dict[str, Any] = json.load(f)
            print(f"Successfully loaded {filename}")
            return data
        except FileNotFoundError:
            print(f"Error: File not found at {filepath}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {filepath}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while loading {filepath}: {e}")
            return None

    def _setup_players(self, num_players: int) -> None:
        """Create and initialize the specified number of players."""
        colors = ["red", "blue", "green", "yellow"]
        for i in range(num_players):
            player_id = f"p{i+1}"
            player_name = f"Player {i+1}"
            player_color = colors[i % len(colors)]
            self.players.append(Player(id=player_id, name=player_name, color=player_color))

    def run_game(self) -> None:
        """Main game loop."""
        print("Starting Full Metal Planet game...")
        
        # Main loop continues as long as the game is not over.
        # game_over is set by _play_game_turn if TurnManager runs out of turns (e.g., for up to 25 turns if so defined).
        while self.turn_manager and not self.game_over:
            self._play_game_turn()
            # The check for game_over (i.e., no more turns) is handled within _play_game_turn
            # when current_turn_def from turn_manager.advance_turn() becomes None.
        
        self._end_game_summary()

    def _display_board_state_matplotlib(self, turn_number: int, filename_suffix: str = "") -> None:
        """Display the current board state using matplotlib, aligned with src.board.py."""
        HEX_RADIUS = BOARD_HEX_SIZE
        HEX_ORIENTATION = math.radians(30) # Corrected for flat-topped, vertex-pointing radius
        FREIGHTER_HEX_RADIUS_FACTOR = 0.7 # Factor to make freighter parts smaller than terrain hexes

        terrain_colors_hex = {
            name: _rgb_to_hex(rgb) for name, rgb in BOARD_TERRAIN_COLORS.items()
        }
        default_terrain_hex = "#FFFFFF"
        ore_color_hex = _rgb_to_hex(BOARD_COLOR_ORE)
        hex_border_color_hex = _rgb_to_hex(BOARD_COLOR_HEX_BORDER)
        text_color_hex = _rgb_to_hex(BOARD_COLOR_TEXT)

        # Player symbolic colors to actual drawing colors for freighters
        PLAYER_FREIGHTER_COLORS_MATPLOTLIB = {
            "red": "#FF0000", "blue": "#0000FF", "green": "#008000", "yellow": "#FFFF00"
        }
        FREIGHTER_BUBBLE_COLORS_MATPLOTLIB = {
            "red": "#FFA0A0", "blue": "#A0A0FF", "green": "#A0FFA0", "yellow": "#FFFFE0"
        }

        fig = plt.figure(figsize=(18, 10))
        ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f"FMP - Turn {turn_number}{filename_suffix}", fontsize=14, pad=5)

        if not self.board or not self.board.hexes:
            print("Warning: No board or hexes found in board object for display.")
            if fig: plt.close(fig)
            return

        all_hex_objects = list(self.board.hexes.values())

        # Calculate extents based on hex_obj.center_x and inverted hex_obj.center_y
        # Pygame y is 0 at top, increases downwards. Matplotlib y is 0 at bottom, increases upwards.
        # To match Pygame visuals, we plot -hex_obj.center_y and adjust limits accordingly.
        min_cx = min(h.center_x for h in all_hex_objects)
        max_cx = max(h.center_x for h in all_hex_objects)
        # For y, since we plot -center_y, min of -center_y is -max(center_y)
        min_plot_y = min(-h.center_y for h in all_hex_objects)
        max_plot_y = max(-h.center_y for h in all_hex_objects)
        
        # Add padding based on hex dimensions for full visibility
        x_padding = HEX_RADIUS * 1.5
        y_padding = (BOARD_HEX_SIZE * math.sqrt(3) / 2) * 1.5 # Hex height * padding factor
        
        ax.set_xlim(min_cx - x_padding, max_cx + x_padding)
        ax.set_ylim(min_plot_y - y_padding, max_plot_y + y_padding) # Use calculated plot y limits

        for hex_obj in all_hex_objects:
            center_x, plot_y = hex_obj.center_x, -hex_obj.center_y # Invert y for plotting
            face_color = terrain_colors_hex.get(hex_obj.terrain, default_terrain_hex)
            
            hexagon = RegularPolygon(
                (center_x, plot_y),
                numVertices=6,
                radius=HEX_RADIUS,
                orientation=HEX_ORIENTATION,
                facecolor=face_color,
                edgecolor=hex_border_color_hex,
                linewidth=1.0, 
                alpha=0.8,
                zorder=1 # Base terrain hexes
            )
            ax.add_patch(hexagon)

            if hex_obj.ore:
                ax.plot(
                    center_x, plot_y, # Use inverted y for ore marker
                    marker='o',
                    color=ore_color_hex,
                    markersize=BOARD_HEX_SIZE / 2.0, # Adjusted for visual match with Pygame radius
                    markeredgecolor=text_color_hex,
                    mew=0.5, # Consider adjusting mew for visual consistency
                    zorder=3
                )
        
        # Draw Zone Borders
        # For flat-topped hexes with RegularPolygon(orientation=math.radians(30)):
        # V0 (30°), V1 (90°), V2 (150°), V3 (210°), V4 (270°), V5 (330°).
        # AXIAL_DIRECTIONS = [(0,-1)N, (1,-1)NE, (1,0)SE, (0,1)S, (-1,1)SW, (-1,-1)NW]
        # Edges facing these directions (indices of vertices forming the edge):
        # N: V1-V2; NE: V0-V1; SE/E: V5-V0; S/SE: V4-V5; SW: V3-V4; NW: V2-V3
        MATPLOTLIB_EDGE_VERTEX_INDICES = [ 
            (1, 2), # 0: North
            (0, 1), # 1: Northeast
            (5, 0), # 2: Southeast (East)
            (4, 5), # 3: South (Southeast)
            (3, 4), # 4: Southwest
            (2, 3)  # 5: Northwest
        ]
        ZONE_BORDER_COLOR_HEX = _rgb_to_hex((0,0,0)) # Black
        ZONE_BORDER_LINEWIDTH = 2.5 # Increased from 2.0
        ZONE_BORDER_ZORDER = 2.0    # Increased from 1.5, above hex faces and their default thin border, below ore/units

        def get_matplotlib_hex_vertices(c_x, c_y, radius, orientation_rad):
            verts = []
            for i in range(6):
                angle = orientation_rad + (2 * math.pi * i / 6)
                verts.append((c_x + radius * math.cos(angle), c_y + radius * math.sin(angle)))
            return verts

        for hex_obj in all_hex_objects:
            if hex_obj.zone_id is None: # Only draw borders for hexes that are part of a zone
                continue

            current_hex_q_axial, current_hex_r_axial = self.board._oddq_to_axial(hex_obj.col, hex_obj.row)
            hex_plot_center_x, hex_plot_center_y = hex_obj.center_x, -hex_obj.center_y # Remember y-inversion
            
            hex_vertices_plot_coords = get_matplotlib_hex_vertices(hex_plot_center_x, hex_plot_center_y, HEX_RADIUS, HEX_ORIENTATION)

            # Only check specific directions to avoid drawing each border twice
            # For example, check N, NE, SE (East) from the current hex.
            # AXIAL_DIRECTIONS indices: 0 (N), 1 (NE), 2 (SE/E)
            for dir_idx in range(3): # Only consider directions 0, 1, 2
                dq, dr = self.board.AXIAL_DIRECTIONS[dir_idx]
                neighbor_q_axial = current_hex_q_axial + dq
                neighbor_r_axial = current_hex_r_axial + dr
                
                n_col, n_row = self.board._axial_to_oddq(neighbor_q_axial, neighbor_r_axial)
                neighbor_hex = self.board.get_hex(n_col, n_row)
                
                is_boundary_edge = False
                # Only draw a border if both hexes exist, both have a zone_id, 
                # and their zone_ids are different.
                if neighbor_hex is not None and \
                   neighbor_hex.zone_id is not None and \
                   hex_obj.zone_id is not None and \
                   neighbor_hex.zone_id != hex_obj.zone_id:
                    is_boundary_edge = True
                
                if is_boundary_edge:
                    v_idx1, v_idx2 = MATPLOTLIB_EDGE_VERTEX_INDICES[dir_idx]
                    point1 = hex_vertices_plot_coords[v_idx1]
                    point2 = hex_vertices_plot_coords[v_idx2]
                    
                    ax.add_line(Line2D([point1[0], point2[0]], [point1[1], point2[1]], 
                                       color=ZONE_BORDER_COLOR_HEX, 
                                       linewidth=ZONE_BORDER_LINEWIDTH, 
                                       zorder=ZONE_BORDER_ZORDER))

        # Draw Freighters
        for player_id_str, landing_info in self.freighter_landings.items():
            player_obj = next((p for p in self.players if p.id == player_id_str), None)
            if not player_obj: continue

            freighter_base_color = PLAYER_FREIGHTER_COLORS_MATPLOTLIB.get(player_obj.color, "#800080") # Default purple
            bubble_draw_color = FREIGHTER_BUBBLE_COLORS_MATPLOTLIB.get(player_obj.color, "#FFC0FF") # Default light purple
            
            occupied_hex_coords = landing_info['occupied_hexes'] # List of (col,row)
            
            # Draw pods first
            for idx, (q_col, r_row) in enumerate(occupied_hex_coords):
                if idx == 0: continue # Skip bubble, draw it last for layering
                hex_obj = self.board.get_hex(q_col, r_row)
                if hex_obj:
                    center_x, plot_y = hex_obj.center_x, -hex_obj.center_y
                    freighter_part_hex = RegularPolygon((center_x, plot_y), numVertices=6, radius=HEX_RADIUS * FREIGHTER_HEX_RADIUS_FACTOR,
                                                        orientation=HEX_ORIENTATION, facecolor=freighter_base_color, 
                                                        edgecolor='black', linewidth=1.2, alpha=0.9, zorder=5)
                    ax.add_patch(freighter_part_hex)
                    ax.text(center_x, plot_y, str(idx), color='white', ha='center', va='center', fontsize=7, fontweight='bold', zorder=7)
            
            # Draw bubble
            if occupied_hex_coords:
                bubble_q_col, bubble_r_row = occupied_hex_coords[0]
                bubble_hex_obj = self.board.get_hex(bubble_q_col, bubble_r_row)
                if bubble_hex_obj:
                    center_x, plot_y = bubble_hex_obj.center_x, -bubble_hex_obj.center_y
                    bubble_graphic = RegularPolygon((center_x, plot_y), numVertices=6, radius=HEX_RADIUS * FREIGHTER_HEX_RADIUS_FACTOR, 
                                                    orientation=HEX_ORIENTATION, facecolor=bubble_draw_color, 
                                                    edgecolor='black', linewidth=1.2, alpha=0.9, zorder=6)
                    ax.add_patch(bubble_graphic)
                    ax.text(center_x, plot_y, player_obj.id.upper()[1:], color='black', ha='center', va='center', fontsize=7, fontweight='bold', zorder=7)

        # Draw Deployed Units
        UNIT_SHORT_CODES = {
            "tank": "T", "barge": "B", "heap": "H", "gunboat": "G",
            "weather_hen": "W", "pontoon": "P", "crab": "C"
        }
        UNIT_MARKER_SHAPES = { # Matplotlib marker styles
            "tank": "s", "heap": "s", # Square
            "barge": "^", "gunboat": "^", # Triangle (up)
            # Others default to circle if not specified here, handled in drawing logic
        }
        UNIT_MARKER_DEFAULT_SHAPE = "o" # Circle
        UNIT_MARKER_S_VALUE = 188 # Direct s value for ax.scatter (marker area) - Increased from 150
        UNIT_MARKER_EDGECOLOR = "black"
        UNIT_MARKER_LINEWIDTH = 0.75
        UNIT_MARKER_ZORDER = 8
        UNIT_TEXT_ZORDER = 9

        for player in self.players:
            player_color_hex = PLAYER_FREIGHTER_COLORS_MATPLOTLIB.get(player.color, "#800080") # Use freighter color for unit marker
            # Determine contrasting text color for readability on player color
            r, g, b = tuple(int(player_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            brightness = (r*299 + g*587 + b*114) / 1000
            unit_text_color = 'white' if brightness < 128 else 'black'

            for unit_instance in player.units_on_board:
                if unit_instance.is_in_freighter: # Skip units not on the board
                    continue
                
                hex_obj = self.board.get_hex(unit_instance.col, unit_instance.row)
                if not hex_obj:
                    print(f"Warning: Could not find hex ({unit_instance.col},{unit_instance.row}) for unit {unit_instance.unit_id}. Skipping draw.")
                    continue
                
                center_x, plot_y = hex_obj.center_x, -hex_obj.center_y # Remember y-inversion for primary hex
                short_code = UNIT_SHORT_CODES.get(unit_instance.unit_type_id, "?")

                # Special drawing for Barge (2-hex unit)
                if unit_instance.unit_type_id == "barge" and unit_instance.second_hex_col is not None and unit_instance.second_hex_row is not None:
                    second_hex_obj = self.board.get_hex(unit_instance.second_hex_col, unit_instance.second_hex_row)
                    if not second_hex_obj:
                        # Fallback: draw barge as a single point if second hex data is bad (should not happen)
                        print(f"Warning: Barge {unit_instance.unit_id} has second_hex coords but object not found. Drawing as single point.")
                        ax.scatter(center_x, plot_y, s=UNIT_MARKER_S_VALUE, marker="^", color=player_color_hex, edgecolors=UNIT_MARKER_EDGECOLOR, linewidths=UNIT_MARKER_LINEWIDTH, zorder=UNIT_MARKER_ZORDER)
                        ax.text(center_x, plot_y, short_code, color=unit_text_color, ha='center', va='center', fontsize=8, fontweight='bold', zorder=UNIT_TEXT_ZORDER)
                    else:
                        sec_center_x, sec_plot_y = second_hex_obj.center_x, -second_hex_obj.center_y
                        
                        mid_x = (center_x + sec_center_x) / 2
                        mid_y = (plot_y + sec_plot_y) / 2
                        angle_rad = math.atan2(sec_plot_y - plot_y, sec_center_x - center_x)
                        angle_deg = math.degrees(angle_rad)

                        # Draw a thick line for the barge body
                        ax.plot([center_x, sec_center_x], [plot_y, sec_plot_y],
                                color=player_color_hex, 
                                linewidth=HEX_RADIUS * 0.8, # Adjust thickness as needed (e.g. 80% of hex radius)
                                solid_capstyle='butt',
                                zorder=UNIT_MARKER_ZORDER - 0.1) # Slightly below other unit markers/text
                        
                        # Draw the short code text at the midpoint, rotated
                        ax.text(mid_x, mid_y, short_code, 
                                color=unit_text_color, 
                                ha='center', va='center', 
                                fontsize=8, fontweight='bold', 
                                rotation=angle_deg, rotation_mode='anchor',
                                zorder=UNIT_TEXT_ZORDER)
                    continue # Important: Skip default scatter plot for this barge

                # Default drawing for single-hex units
                marker_shape = UNIT_MARKER_SHAPES.get(unit_instance.unit_type_id, UNIT_MARKER_DEFAULT_SHAPE)
                ax.scatter(center_x, plot_y, 
                           s=UNIT_MARKER_S_VALUE, 
                           marker=marker_shape, 
                           color=player_color_hex, 
                           edgecolors=UNIT_MARKER_EDGECOLOR,
                           linewidths=UNIT_MARKER_LINEWIDTH,
                           zorder=UNIT_MARKER_ZORDER)

                # Draw the short code text for single hex units
                ax.text(center_x, plot_y, short_code, 
                        color=unit_text_color, 
                        ha='center', va='center', 
                        fontsize=8, fontweight='bold', 
                        zorder=UNIT_TEXT_ZORDER)

        legend_elements = [
            Patch(facecolor=terrain_colors_hex.get('plain', default_terrain_hex), label='Plain'),
            Patch(facecolor=terrain_colors_hex.get('swamp', default_terrain_hex), label='Swamp'),
            Patch(facecolor=terrain_colors_hex.get('sea', default_terrain_hex), label='Sea'),
            Patch(facecolor=terrain_colors_hex.get('mountain', default_terrain_hex), label='Mountain'),
            Patch(facecolor=terrain_colors_hex.get('reef', default_terrain_hex), label='Reef'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor=ore_color_hex,
                  markeredgecolor=text_color_hex, markersize=BOARD_HEX_SIZE / 2.0, label='Ore') # Match ore marker size
        ]
        
        for player_id_str, landing_info in self.freighter_landings.items():
            player_obj = next((p for p in self.players if p.id == player_id_str), None)
            if player_obj:
                 legend_elements.append(Patch(facecolor=PLAYER_FREIGHTER_COLORS_MATPLOTLIB.get(player_obj.color, "#800080"), 
                                            label=f'{player_obj.name} Freighter'))

        legend = ax.legend(
            handles=legend_elements,
            loc='center left',
            bbox_to_anchor=(1, 0.9),
            fontsize='x-small',
            framealpha=0.9,
            borderpad=0.3,
            handletextpad=0.3,
            columnspacing=0.5,
            labelspacing=0.2
        )

        # List units in freighter on the side of the plot
        # Position text to the right of the main map content and legend
        freighter_text_y_start = 0.80  # Adjusted y start, below potential new legend position
        freighter_text_x_start = 1.02  # Relative to right edge of the axes (just outside)
        line_spacing_factor = 0.03 # Relative to axes height

        text_lines_freighter = ["Units in Freighter:"]
        for player in self.players:
            if player.units_in_freighter:
                text_lines_freighter.append(f"- {player.name} ({player.color}):")
                counts = {}
                for unit in player.units_in_freighter:
                    counts[unit.unit_type_id] = counts.get(unit.unit_type_id, 0) + 1
                for unit_type_id, num in counts.items():
                    text_lines_freighter.append(f"    {num}x {unit_type_id}")
        
        if len(text_lines_freighter) > 1: # Only add if there are units to list
            for i, line in enumerate(text_lines_freighter):
                ax.text(freighter_text_x_start, 
                        freighter_text_y_start - i * line_spacing_factor, 
                        line, 
                        transform=ax.transAxes, # Position relative to axes bounding box
                        fontsize='xx-small', ha='left', va='top', color='black')

        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, f"board_turn_{turn_number}{filename_suffix}.png")
        try:
            plt.savefig(save_path, bbox_inches='tight', dpi=150, pad_inches=0.02)
            print(f"Board state image saved to {save_path}")
        except Exception as e:
            print(f"Error saving matplotlib figure: {e}")
        finally:
            if fig: plt.close(fig)

    def _play_game_turn(self) -> None:
        """Handle a single game turn."""
        current_turn_def = self.turn_manager.advance_turn()
        if current_turn_def is None:
            self.game_over = True
            return

        print(f"\n{'='*10} GAME TURN {current_turn_def.number}: {current_turn_def.name} {'='*10}")
        
        if self.tide_deck:
            self.tide_deck.advance_turn_tide(current_turn_def.number)
            current_tide = self.tide_deck.current_tide_card
            print(f"Current Tide: {current_tide.name if current_tide else 'None'} "
                  f"(Type: {current_tide.type if current_tide else 'N/A'})")

        if current_turn_def.number == 1:
            self._handle_turn_1_arrival()
        elif current_turn_def.number == 2:
            self._handle_turn_2_deployment()
        else:
            # For now, player actions will occur on all turns > 0 if not special
            for _ in range(len(self.players)):
                current_player = self.players[self.current_player_index]
                print(f"\n--- {current_player.name}'s Turn ---")
                
                current_player.prepare_for_new_turn(current_turn_def.action_points)
                print(f"Available AP: {current_player._total_ap_for_spending_this_turn}")
                
                self._handle_player_actions(current_player, current_turn_def)
                current_player.end_turn_banking_ap()
                
                print(f"--- {current_player.name}'s Turn Ends. Final Banked AP: {current_player.action_points_banked} ---")
                
                self.current_player_index = (self.current_player_index + 1) % len(self.players)

        self._display_board_state_matplotlib(current_turn_def.number, filename_suffix=f"_end_of_turn_{current_turn_def.number}")
        print(f"\n{'='*10} END OF GAME TURN {current_turn_def.number} {'='*10}")

        if current_turn_def.number == 2: # Stop after Turn 2
            print("Simulation configured to stop after Turn 2.")
            self.game_over = True

    def _handle_turn_1_arrival(self) -> None:
        print("\nHandling Turn 1: Freighter Arrival phase.")
        if 'starfreighter' not in self.unit_types or not self.unit_types['starfreighter'].pod_shapes:
            print("Error: Starfreighter unit type or its pod_shapes not defined in unit_data. Cannot land freighters.")
            return

        starfreighter_type = self.unit_types['starfreighter']
        mainland_zones = [str(i) for i in range(1, 13)]
        island_zones = ["13", "14"]
        all_landing_zones = mainland_zones + island_zones

        for player in self.players:
            print(f"\n--- {player.name}'s Freighter Landing ---")
            forbidden_zones = set(self.landed_freighter_zones)
            for landed_z in self.landed_freighter_zones:
                forbidden_zones.update(self._get_adjacent_zone_ids(landed_z))
            
            available_zones = [z for z in all_landing_zones if z not in forbidden_zones]
            if not available_zones:
                print(f"Error: No valid landing zones available for {player.name}!")
                continue

            chosen_zone_id = random.choice(available_zones)
            # Pod shape will be determined after finding a bubble candidate
            print(f"{player.name} targeting Zone {chosen_zone_id}")

            possible_bubble_hexes_in_zone = []
            if self.board and hasattr(self.board, 'get_hexes_in_zone'):
                possible_bubble_hexes_in_zone = self.board.get_hexes_in_zone(chosen_zone_id)
            else:
                print(f"Warning: board.get_hexes_in_zone not found. Falling back to iterating all hexes for zone {chosen_zone_id}.")
                if self.board:
                    possible_bubble_hexes_in_zone = [h for h in self.board.hexes.values() if h.zone_id == chosen_zone_id]

            found_spot = False
            random.shuffle(possible_bubble_hexes_in_zone) 

            for bubble_candidate_hex in possible_bubble_hexes_in_zone:
                if found_spot: break # Already found a spot for this player

                if bubble_candidate_hex.terrain not in ['plain', 'swamp']:
                    continue
                
                # Now, for this bubble candidate, try each available pod shape
                # Make a copy of the pod shapes and shuffle it for random testing order
                shuffled_pod_shapes = list(starfreighter_type.pod_shapes)
                random.shuffle(shuffled_pod_shapes)

                for pod_shape_obj in shuffled_pod_shapes:
                    chosen_pod_angles = pod_shape_obj.pod_angles
                    print(f"  Trying pod shape {chosen_pod_angles} for bubble at ({bubble_candidate_hex.col},{bubble_candidate_hex.row})")

                    potential_freighter_coords = self.board.place_freighter(bubble_candidate_hex.col, bubble_candidate_hex.row, chosen_pod_angles)
                    if len(potential_freighter_coords) != 4:
                        # print(f"    DEBUG: Invalid freighter shape generated. Skipping shape.")
                        continue

                    valid_placement = True
                    current_all_landed_hexes = {coord for landing in self.freighter_landings.values() for coord in landing['occupied_hexes']}

                    for i, (p_col, p_row) in enumerate(potential_freighter_coords):
                        hex_obj = self.board.get_hex(p_col, p_row)
                        if not hex_obj or hex_obj.terrain not in ['plain', 'swamp'] or (p_col, p_row) in current_all_landed_hexes:
                            valid_placement = False
                            # print(f"    DEBUG: Invalid hex for part at ({p_col},{p_row}). Terrain: {hex_obj.terrain if hex_obj else 'N/A'}, Occupied: {(p_col, p_row) in current_all_landed_hexes}. Skipping shape.")
                            break
                    if not valid_placement:
                        continue # Try next pod shape for this bubble candidate
                    
                    # New Check: Ensure all pods are in the same zone as the bubble
                    bubble_zone_id = chosen_zone_id # The zone targeted for the bubble
                    for i, (p_col, p_row) in enumerate(potential_freighter_coords):
                        if i == 0: # Skip the bubble itself, its zone is implicitly chosen_zone_id
                            continue
                        pod_hex = self.board.get_hex(p_col, p_row)
                        # We already checked if pod_hex exists and has valid terrain.
                        # Here, we only care if it's in a *different* zone.
                        # If pod_hex.zone_id is None, it's not in *another* identified zone, so that's fine.
                        # If it has a zone_id, it must match the bubble's zone_id.
                        if pod_hex and pod_hex.zone_id is not None and pod_hex.zone_id != bubble_zone_id:
                            valid_placement = False
                            print(f"    DEBUG: Pod at ({p_col},{p_row}) in zone {pod_hex.zone_id} which is different from bubble zone {bubble_zone_id}. Skipping shape.")
                            break
                    if not valid_placement:
                        continue # Try next pod shape for this bubble candidate
                    
                    # New Check: Ensure no part of the freighter is on an edge hex
                    for p_col, p_row in potential_freighter_coords:
                        if self.board.is_edge_hex(p_col, p_row):
                            valid_placement = False
                            print(f"    DEBUG: Freighter part at ({p_col},{p_row}) is on map edge. Skipping shape.")
                            break
                    if not valid_placement:
                        continue # Try next pod shape for this bubble candidate
                    
                    # Landed!
                    self.freighter_landings[player.id] = {
                        'zone_id': chosen_zone_id,
                        'occupied_hexes': potential_freighter_coords,
                        'pod_shape_angles': chosen_pod_angles # Store the successful shape
                    }
                    self.landed_freighter_zones.add(chosen_zone_id)
                    player.freighter_landed = True
                    print(f"Success! {player.name} landed in Zone {chosen_zone_id} at bubble ({bubble_candidate_hex.col},{bubble_candidate_hex.row}) with shape {chosen_pod_angles}. Hexes: {potential_freighter_coords}")
                    
                    hexes_in_zone_to_clear_ore = [h for h in self.board.hexes.values() if h.zone_id == chosen_zone_id]
                    for hex_to_clear in hexes_in_zone_to_clear_ore:
                        if hex_to_clear.ore:
                            hex_to_clear.ore = False
                            print(f"Cleared ore from hex ({hex_to_clear.col}, {hex_to_clear.row}) in Zone {chosen_zone_id}.")

                    # Use a fixed suffix for in-progress Turn 1 landing displays to overwrite.
                    filename_suffix_for_landing_display = "_turn_1_freighter_landing_in_progress"
                    self._display_board_state_matplotlib(self.turn_manager.current_turn_number, filename_suffix_for_landing_display)
                    found_spot = True
                    break # Break from pod_shape_obj loop (successfully placed with this shape)
            
            if not found_spot:
                print(f"Critical: Could not find a valid landing spot for {player.name} in any available zone after trying Zone {chosen_zone_id}. This may halt game setup.")
                # Potentially add logic here to try another zone for the player if desired, or mark player as unable to land.

    def _handle_turn_2_deployment(self) -> None:
        """Handle the unit deployment phase of Turn 2."""
        print("\nHandling Turn 2: Unit Deployment phase.")
        
        initial_units = {
            "barge": 1,
            "crab": 1,
            "weather_hen": 1,
            "gunboat": 2,
            "tank": 4,
            "heap": 1,
            "pontoon": 1
        }
        
        for player in self.players:
            print(f"\n--- {player.name}'s Unit Deployment ---")
            player.initial_unit_pool = initial_units.copy()
            print(f"Initial unit pool for {player.name}: {player.initial_unit_pool}")
            print(f"Player {player.id} needs to deploy initial units.")
            # Actual deployment logic will be implemented later
            # For now, just acknowledge and list units
            print(f"Player {player.id} landing zone: {self.freighter_landings.get(player.id, {'zone_id': None})['zone_id'] if self.freighter_landings.get(player.id, {'zone_id': None})['zone_id'] else 'N/A'}")

            if not self.freighter_landings.get(player.id, {'zone_id': None})['zone_id']:
                print(f"Warning: Player {player.id} has no landing zone information. Cannot deploy units.")
                continue

            zone_hexes = self.board.get_hexes_in_zone(self.freighter_landings[player.id]['zone_id'])
            if not zone_hexes:
                print(f"Warning: No hexes found in landing zone {self.freighter_landings[player.id]['zone_id']} for Player {player.id}. Cannot deploy units.")
                continue
            
            # Keep track of hexes occupied during this deployment phase to avoid stacking in same hex
            occupied_this_turn_deployment: Set[Tuple[int, int]] = set()
            # Add freighter hexes to the occupied set for this player
            if player.id in self.freighter_landings:
                freighter_hex_coords = self.freighter_landings[player.id].get('occupied_hexes', [])
                for f_col, f_row in freighter_hex_coords:
                    occupied_this_turn_deployment.add((f_col, f_row))
                print(f"Player {player.id} freighter occupies: {freighter_hex_coords}. These are blocked for deployment.")

            for unit_type_id, count in player.initial_unit_pool.items():
                unit_type = self.unit_types.get(unit_type_id)
                if not unit_type:
                    print(f"Warning: Unit type '{unit_type_id}' not found in game data. Cannot deploy for Player {player.id}.")
                    continue

                for _ in range(count): # Deploy each unit of this type
                    deployed_this_instance = False
                    # Attempt to find a valid hex for deployment (simple greedy approach for now)
                    # Shuffle zone_hexes to get some variability in placement if multiple spots are valid
                    random.shuffle(zone_hexes)

                    for hex_candidate in zone_hexes:
                        if (hex_candidate.col, hex_candidate.row) in occupied_this_turn_deployment:
                            continue # Already placed a unit here this turn
                        
                        # 1. Check terrain suitability for the primary hex
                        if hex_candidate.terrain not in unit_type.can_enter:
                            continue

                        # 2. Coastal check for specific units (primary hex must be coastal for barge)
                        primary_hex_is_coastal = False
                        if unit_type_id in ["barge", "gunboat"]:
                            neighbors = self.board.get_neighbors(hex_candidate)
                            for neighbor in neighbors:
                                if neighbor.terrain == 'sea':
                                    primary_hex_is_coastal = True
                                    break
                            if not primary_hex_is_coastal:
                                continue
                        
                        # 3. Multi-hex unit placement (specifically for Barge)
                        second_hex_coords: Optional[Tuple[int, int]] = None
                        if unit_type_id == "barge":
                            found_second_barge_hex = False
                            # The primary hex_candidate must not be an edge hex for a 2-hex unit
                            if self.board.is_edge_hex(hex_candidate.col, hex_candidate.row):
                                continue # Primary hex for barge cannot be on map edge

                            possible_second_hexes = self.board.get_neighbors(hex_candidate)
                            random.shuffle(possible_second_hexes) # Check neighbors in random order

                            for adj_hex in possible_second_hexes:
                                # Second hex must not be an edge hex
                                if self.board.is_edge_hex(adj_hex.col, adj_hex.row):
                                    continue
                                # Second hex must not be already occupied this turn
                                if (adj_hex.col, adj_hex.row) in occupied_this_turn_deployment:
                                    continue
                                # Second hex must not be part of the freighter
                                # (already covered by occupied_this_turn_deployment if freighter hexes were added)
                                
                                # Second hex for barge can be 'sea' or valid land in the same zone
                                valid_second_hex_terrain = False
                                if adj_hex.terrain == 'sea':
                                    valid_second_hex_terrain = True
                                elif adj_hex.terrain in unit_type.can_enter and adj_hex.zone_id == hex_candidate.zone_id:
                                    valid_second_hex_terrain = True
                                
                                if valid_second_hex_terrain:
                                    second_hex_coords = (adj_hex.col, adj_hex.row)
                                    found_second_barge_hex = True
                                    break # Found a valid second hex for the barge
                            
                            if not found_second_barge_hex:
                                continue # Could not find a suitable second hex for the barge
                        
                        # If all checks pass, deploy the unit
                        new_unit_id = uuid.uuid4().hex
                        deployed_unit = Unit(
                            unit_id=new_unit_id, 
                            unit_type_id=unit_type_id, 
                            player_id=player.id, 
                            col=hex_candidate.col, 
                            row=hex_candidate.row,
                            second_hex_col=second_hex_coords[0] if second_hex_coords else None,
                            second_hex_row=second_hex_coords[1] if second_hex_coords else None,
                            is_in_freighter=False
                        )
                        
                        player.units_on_board.append(deployed_unit)
                        occupied_this_turn_deployment.add((hex_candidate.col, hex_candidate.row))
                        if second_hex_coords:
                            occupied_this_turn_deployment.add(second_hex_coords)
                            print(f"Player {player.id} deployed {unit_type_id} (ID: {new_unit_id[:6]}...) at ({hex_candidate.col},{hex_candidate.row}) & ({second_hex_coords[0]},{second_hex_coords[1]}) in Zone {self.freighter_landings[player.id]['zone_id']}.")
                        else:
                            print(f"Player {player.id} deployed {unit_type_id} (ID: {new_unit_id[:6]}...) at ({hex_candidate.col},{hex_candidate.row}) in Zone {self.freighter_landings[player.id]['zone_id']}.")
                        
                        deployed_this_instance = True
                        break # Break from hex_candidate loop, deployed this specific unit instance
                    
                    if not deployed_this_instance:
                        print(f"Warning: Player {player.id} could not find a suitable spot to deploy an instance of {unit_type_id} in Zone {self.freighter_landings[player.id]['zone_id']}. Unit remains in freighter.")
                        # Create a Unit instance and mark it as in_freighter
                        # Assign a nominal/non-board location, or freighter's bubble location
                        freighter_bubble_col, freighter_bubble_row = -1, -1 # Default if no landing info
                        if player.id in self.freighter_landings and self.freighter_landings[player.id]['occupied_hexes']:
                            freighter_bubble_col, freighter_bubble_row = self.freighter_landings[player.id]['occupied_hexes'][0]
                        
                        reserve_unit_id = uuid.uuid4().hex
                        unit_staying_in_freighter = Unit(
                            unit_id=reserve_unit_id,
                            unit_type_id=unit_type_id,
                            player_id=player.id,
                            col=freighter_bubble_col, # Or some other off-map/nominal location
                            row=freighter_bubble_row,
                            is_in_freighter=True
                        )
                        player.units_in_freighter.append(unit_staying_in_freighter)
            
            # Initial_unit_pool represents the units to *attempt* to deploy this turn.
            # After the loop, it will be empty as all have been processed (either deployed or moved to units_in_freighter)
            player.initial_unit_pool.clear()
            print(f"Player {player.id} deployment phase complete. Deployed: {len(player.units_on_board)}, In Freighter: {len(player.units_in_freighter)}")

    def _handle_player_actions(self, player: Player, turn_def: TurnDefinition) -> None:
        """Handle a player's actions during their turn."""
        print(f"Player {player.id} takes actions...")
        
        if turn_def.action_points > 0 and player._total_ap_for_spending_this_turn > 0:
            max_spend = min(player._total_ap_for_spending_this_turn, 
                          turn_def.action_points // 2 if turn_def.action_points > 1 else 1)
            # Ensure max_spend is at least 0, and if positive, randint has valid range
            ap_to_spend = 0
            if max_spend > 0:
                 ap_to_spend = random.randint(0, max_spend) # Can spend 0 AP
            
            if ap_to_spend > 0: # Only attempt to spend if ap_to_spend is positive
                if player.spend_ap(ap_to_spend):
                    print(f"Player {player.id} (simulated) spent {ap_to_spend} AP.")
                else:
                    print(f"Player {player.id} failed to spend {ap_to_spend} AP (Not enough AP or other issue).")
            else:
                print(f"Player {player.id} (simulated) spent 0 AP.")

    def _end_game_summary(self) -> None:
        """Handle end of game summary and scoring."""
        print("\nGame Over. Calculating scores...")
        # Score calculation to be implemented later 

    def _get_adjacent_zone_ids(self, zone_id_str: str) -> List[str]:
        if not zone_id_str or zone_id_str in ["13", "14"]: return [] # Islands have no land-adjacent zones for freighter placement conflicts
        try:
            zone_int = int(zone_id_str)
            if 1 <= zone_int <= 12: # Mainland zones form a circle
                prev_zone = str((zone_int - 2 + 12) % 12 + 1)
                next_zone = str((zone_int % 12) + 1)
                return [prev_zone, next_zone]
        except ValueError:
            print(f"Warning: Invalid zone_id '{zone_id_str}' for adjacency calculation.")
        return []

    # Removed _is_valid_edge_passage as its intent is replaced by the direct is_edge_hex check for landing

    # ... (rest of the class, like _display_board_state_matplotlib etc.) 