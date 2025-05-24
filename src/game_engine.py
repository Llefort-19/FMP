import json
import os
import random
import math
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon, Patch, Circle
from matplotlib.lines import Line2D
from typing import List, Dict, Any, Optional, Tuple, Set
import uuid # Add uuid for unique unit IDs

from .board import (
    Board, 
    HEX_SIZE as BOARD_HEX_SIZE, 
    TERRAIN_COLORS as BOARD_TERRAIN_COLORS, 
    COLOR_ORE as BOARD_COLOR_ORE,
    COLOR_HEX_BORDER as BOARD_COLOR_HEX_BORDER,
    COLOR_TEXT as BOARD_COLOR_TEXT
)
from .units import UnitType, Unit
from .tides import TideDeck, TideCard # Added TideCard
from .turn_manager import TurnManager, TurnDefinition
from .player import Player
from .game_state import GameState # Added GameState

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

        # Initialize game components that will be part of GameState or used to create it
        board_map_path = os.path.join(ASSET_PATH, "board.json")
        # board object is created here, then passed to GameState
        board_obj = Board(map_file_path=board_map_path) # Renamed to avoid conflict
        
        self.tide_deck = TideDeck(self.tide_cards_data) if self.tide_cards_data else None
        self.turn_manager = TurnManager(self.turns_data) if self.turns_data else None
        
        # Initialize unit types (will be part of GameState)
        unit_types_dict: Dict[str, UnitType] = {}
        if self.unit_data:
            raw_unit_list = self.unit_data.get('units', [])
            for unit_dict_item in raw_unit_list: # Renamed to avoid conflict
                if 'id' not in unit_dict_item:
                    print(f"Warning: Unit data missing 'id': {unit_dict_item}. Skipping.")
                    continue
                try:
                    unit_type_obj = UnitType.from_dict(unit_dict_item)
                    unit_types_dict[unit_type_obj.id] = unit_type_obj
                except Exception as e:
                    print(f"Error processing unit data for ID '{unit_dict_item.get('id')}': {e}")

        # Initialize players (will be part of GameState)
        players_list: List[Player] = []
        player_colors = ["red", "blue", "green", "yellow"] # Renamed to avoid conflict
        for i in range(num_players):
            player_id = f"p{i+1}"
            player_name = f"Player {i+1}"
            player_color = player_colors[i % len(player_colors)]
            players_list.append(Player(id=player_id, name=player_name, color=player_color))
        
        initial_tide_str = "mid" # Default
        if self.tide_deck:
            fixed_turn_1_type = self.tide_deck.fixed_turns.get("1", "normal")
            if fixed_turn_1_type == "normal": initial_tide_str = "mid"
            elif fixed_turn_1_type in ["low", "high"]: initial_tide_str = fixed_turn_1_type
            # else: initial_tide_str = "mid" # Fallback already set

        all_units_by_id: Dict[str, Unit] = {} # Starts empty, populated during gameplay

        self.state = GameState(
            board=board_obj,
            tide_state=initial_tide_str,
            units_by_id=all_units_by_id, 
            players=players_list,
            unit_types_data=unit_types_dict,
            turn_number=1
        )

        if 'starfreighter' in self.state.unit_types_data:
            sf_type = self.state.unit_types_data['starfreighter']
            # print(f"DEBUG ENGINE INIT (GameState): Starfreighter Pod Shape 0: {sf_type.pod_shapes[0].pod_angles}")
            initial_tide_str = "mid" # Default
            if sf_type.pod_shapes:
                # print(f"DEBUG ENGINE INIT (GameState): Starfreighter Pod Shape 0: {sf_type.pod_shapes[0].pod_angles}") # Commented out this line
                pass # Added pass to avoid indentation error
            # ... (rest of starfreighter debug prints)
        
        self.current_player_index: int = 0
        self.freighter_landings: Dict[str, Dict[str, Any]] = {} 
        self.landed_freighter_zones: Set[str] = set()
        self.game_over: bool = False
        print(f"GameEngine initialized for {num_players} players. GameState created.")

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
        """This method is now integrated into __init__ for GameState setup."""
        pass

    def run_game(self) -> None:
        """Main game loop."""
        print("Starting Full Metal Planet game...")
        
        while self.turn_manager and not self.game_over:
            self._play_game_turn()
        
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

        # Define Zone Border properties
        ZONE_BORDER_COLOR_HEX = _rgb_to_hex((0,0,0)) # Black
        ZONE_BORDER_LINEWIDTH = 2.0 # Adjusted from 2.5 for potentially cleaner look, can be tuned
        ZONE_BORDER_ZORDER = 2.0    # Ensure it's drawn above terrain but below units/freighters if needed

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

        if not self.state.board or not self.state.board.hexes: # USE self.state.board
            print("Warning: No board or hexes found in game_state.board object for display.")
            if fig: plt.close(fig)
            return

        all_hex_objects = list(self.state.board.hexes.values()) # USE self.state.board

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
        # Vertices V0(30°), V1(90°), V2(150°), V3(210°), V4(270°), V5(330°).
        # self.board.AXIAL_DIRECTIONS from board.py is:
        # [(0,-1)N, (+1,-1)NE, (+1,0)SE/E, (0,+1)S, (-1,+1)SW, (-1,0)NW/W]
        # The old MATPLOTLIB_EDGE_VERTEX_INDICES is no longer used.

        for hex_obj in all_hex_objects:
            if hex_obj.zone_id is None: # Only draw borders for hexes that are part of a zone
                continue

            current_hex_q_axial, current_hex_r_axial = self.state.board._oddq_to_axial(hex_obj.col, hex_obj.row)
            hex_plot_center_x, hex_plot_center_y = hex_obj.center_x, -hex_obj.center_y # Remember y-inversion
            
            # The old hex_vertices_plot_coords is no longer needed here.

            # Only check specific directions to avoid drawing each border twice.
            # board.AXIAL_DIRECTIONS[0] is (0,-1) -> N
            # board.AXIAL_DIRECTIONS[1] is (+1,-1) -> NE
            # board.AXIAL_DIRECTIONS[2] is (+1,0) -> SE/E
            for dir_idx in range(3): # Only consider directions N, NE, SE/E from current hex
                dq, dr = self.state.board.AXIAL_DIRECTIONS[dir_idx]
                neighbor_q_axial = current_hex_q_axial + dq
                neighbor_r_axial = current_hex_r_axial + dr
                
                n_col, n_row = self.state.board._axial_to_oddq(neighbor_q_axial, neighbor_r_axial)
                neighbor_hex = self.state.board.get_hex(n_col, n_row)
                
                is_boundary_edge = False
                # Only draw a border if both hexes exist, both have a zone_id, 
                # and their zone_ids are different.
                if neighbor_hex is not None and \
                   neighbor_hex.zone_id is not None and \
                   hex_obj.zone_id is not None and \
                   neighbor_hex.zone_id != hex_obj.zone_id:
                    is_boundary_edge = True
                
                if is_boundary_edge:
                    # Get centers of both hexes (current hex's plot centers are already inverted for y)
                    center1_x, center1_y = hex_plot_center_x, hex_plot_center_y
                    center2_x, center2_y = neighbor_hex.center_x, -neighbor_hex.center_y # Invert neighbor's y for Matplotlib

                    # Compute midpoint of the line connecting the two hex centers
                    mid_x = (center1_x + center2_x) / 2
                    mid_y = (center1_y + center2_y) / 2

                    # Compute vector from center1 to center2
                    dx = center2_x - center1_x
                    dy = center2_y - center1_y
                    
                    edge_len = math.hypot(dx, dy)
                    if edge_len == 0: # Should not happen for distinct hexes
                        continue 

                    # Normalize and rotate 90° to get perpendicular vector for the border mark
                    # This vector points along the border line itself
                    perp_dx = -dy / edge_len
                    perp_dy = dx / edge_len

                    # Define the length of the border mark (e.g., 80% of hex radius)
                    mark_half_len = HEX_RADIUS * 0.4 # User suggested 0.4, total length 0.8 * HEX_RADIUS

                    # Calculate endpoints of the border mark
                    x0 = mid_x - perp_dx * mark_half_len
                    y0 = mid_y - perp_dy * mark_half_len
                    x1 = mid_x + perp_dx * mark_half_len
                    y1 = mid_y + perp_dy * mark_half_len
                    
                    border_line = Line2D([x0, x1], [y0, y1],
                                       color=ZONE_BORDER_COLOR_HEX,
                                       linewidth=ZONE_BORDER_LINEWIDTH,
                                       zorder=ZONE_BORDER_ZORDER)
                    # border_line.set_linestyle('solid') # Ensure solid lines if needed, but default should be solid
                    ax.add_line(border_line)

        # Draw Freighters
        for player_id_str, landing_info in self.freighter_landings.items():
            player_obj = next((p for p in self.state.players if p.id == player_id_str), None)
            if not player_obj: continue

            freighter_base_color = PLAYER_FREIGHTER_COLORS_MATPLOTLIB.get(player_obj.color, "#800080") # Default purple
            bubble_draw_color = FREIGHTER_BUBBLE_COLORS_MATPLOTLIB.get(player_obj.color, "#FFC0FF") # Default light purple
            
            occupied_hex_coords = landing_info['occupied_hexes'] # List of (col,row)
            
            # Draw pods first
            for idx, (q_col, r_row) in enumerate(occupied_hex_coords):
                if idx == 0: continue # Skip bubble, draw it last for layering
                hex_obj = self.state.board.get_hex(q_col, r_row)
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
                bubble_hex_obj = self.state.board.get_hex(bubble_q_col, bubble_r_row)
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

        for unit_instance in self.state.units_by_id.values(): # USE self.state.units_by_id
            if unit_instance.is_in_freighter: 
                continue
            
            player_obj = next((p for p in self.state.players if p.id == unit_instance.player_id), None) # USE self.state.players
            if not player_obj:
                print(f"Warning: Player {unit_instance.player_id} not found for unit {unit_instance.unit_id}. Skipping draw.")
                continue
            
            player_color_hex = PLAYER_FREIGHTER_COLORS_MATPLOTLIB.get(player_obj.color, "#800080")
            r_val, g_val, b_val = tuple(int(player_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            brightness = (r_val*299 + g_val*587 + b_val*114) / 1000
            unit_text_color = 'white' if brightness < 128 else 'black'

            hex_obj = self.state.board.get_hex(unit_instance.col, unit_instance.row) # USE self.state.board
            if not hex_obj:
                print(f"Warning: Could not find hex ({unit_instance.col},{unit_instance.row}) for unit {unit_instance.unit_id}. Skipping draw.")
                continue
            
            center_x, plot_y = hex_obj.center_x, -hex_obj.center_y # Renamed
            short_code = UNIT_SHORT_CODES.get(unit_instance.unit_type_id, "?")

            # Special drawing for Barge (2-hex unit)
            if unit_instance.unit_type_id == "barge" and unit_instance.second_hex_col is not None and unit_instance.second_hex_row is not None:
                second_hex_obj = self.state.board.get_hex(unit_instance.second_hex_col, unit_instance.second_hex_row) # USE self.state.board
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
            player_obj = next((p for p in self.state.players if p.id == player_id_str), None)
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
        for player in self.state.players:
            player_units_in_freighter = [u for u_id, u in self.state.units_by_id.items() if u.player_id == player.id and u.is_in_freighter] # USE self.state.units_by_id
            if player_units_in_freighter:
                text_lines_freighter.append(f"- {player.name} ({player.color}):")
                counts = {}
                for unit_item in player_units_in_freighter: # Renamed to avoid conflict
                    counts[unit_item.unit_type_id] = counts.get(unit_item.unit_type_id, 0) + 1
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

        self.state.turn_number = current_turn_def.number # Update GameState turn number

        print(f"\n{'='*10} GAME TURN {self.state.turn_number}: {current_turn_def.name} {'='*10}")
        
        if self.tide_deck:
            self.tide_deck.advance_turn_tide(self.state.turn_number)
            current_tide_card = self.tide_deck.current_tide_card
            
            # Update GameState tide_state
            if current_tide_card:
                if current_tide_card.type == "normal":
                    self.state.tide_state = "mid"
                elif current_tide_card.type in ["low", "high"]:
                    self.state.tide_state = current_tide_card.type
                else:
                    self.state.tide_state = "mid" # Default for unknown types
                print(f"Current Tide: {current_tide_card.name} (Type: {current_tide_card.type} -> GameState: {self.state.tide_state})")
            else:
                print(f"Current Tide: None (GameState: {self.state.tide_state})")
            
            self.state.board.apply_tide_effects(self.state) # Pass GameState

        if self.state.turn_number == 1:
            self._handle_turn_1_arrival()
        elif self.state.turn_number == 2:
            self._handle_turn_2_deployment()
            # After deployment, units are on board or in freighter, update GameState.units_by_id
            current_units_by_id: Dict[str, Unit] = {}
            for p in self.state.players:
                for unit_obj in p.units_on_board: # These were populated in _handle_turn_2_deployment
                    current_units_by_id[unit_obj.unit_id] = unit_obj
                for unit_obj in p.units_in_freighter: # Also populated there
                    current_units_by_id[unit_obj.unit_id] = unit_obj
            self.state.units_by_id = current_units_by_id
            print(f"GameState.units_by_id updated after Turn 2 deployment. Total units: {len(self.state.units_by_id)}")
        else:
            # For turns > 2
            for _ in range(len(self.state.players)):
                current_player = self.state.players[self.current_player_index]
                print(f"\n--- {current_player.name}'s Turn ---")
                
                current_player.prepare_for_new_turn(current_turn_def.action_points)
                print(f"Available AP: {current_player._total_ap_for_spending_this_turn}")
                
                self._handle_player_actions(current_player, current_turn_def) # Will be updated in TASK 7
                current_player.end_turn_banking_ap()
                
                print(f"--- {current_player.name}'s Turn Ends. Final Banked AP: {current_player.action_points_banked} ---")
                self.current_player_index = (self.current_player_index + 1) % len(self.state.players)

        self._display_board_state_matplotlib(self.state.turn_number, filename_suffix=f"_end_of_turn_{self.state.turn_number}")
        print(f"\n{'='*10} END OF GAME TURN {self.state.turn_number} {'='*10}")

        if self.state.turn_number == 2: # Stop after Turn 2 (as per original logic)
            print("Simulation configured to stop after Turn 2.")
            self.game_over = True

    def _handle_turn_1_arrival(self) -> None:
        print("\nHandling Turn 1: Freighter Arrival phase.")
        if 'starfreighter' not in self.state.unit_types_data or not self.state.unit_types_data['starfreighter'].pod_shapes:
            print("Error: Starfreighter unit type or its pod_shapes not defined. Cannot land freighters.")
            return

        starfreighter_type = self.state.unit_types_data['starfreighter']
        mainland_zones = [str(i) for i in range(1, 13)]
        island_zones = ["13", "14"]
        all_landing_zones = mainland_zones + island_zones
        
        for player in self.state.players:
            print(f"\n--- {player.name}'s Freighter Landing ---")
            forbidden_zones = set(self.landed_freighter_zones)
            for landed_z in self.landed_freighter_zones:
                forbidden_zones.update(self._get_adjacent_zone_ids(landed_z))
            
            available_zones = [z for z in all_landing_zones if z not in forbidden_zones]
            if not available_zones:
                print(f"Error: No valid landing zones available for {player.name}!")
                continue
            
            chosen_zone_id = random.choice(available_zones)
            print(f"{player.name} targeting Zone {chosen_zone_id}")

            possible_bubble_hexes_in_zone = []
            if self.state.board and hasattr(self.state.board, 'get_hexes_in_zone'):
                possible_bubble_hexes_in_zone = self.state.board.get_hexes_in_zone(chosen_zone_id)
            else:
                if self.state.board:
                    possible_bubble_hexes_in_zone = [h for h in self.state.board.hexes.values() if h.zone_id == chosen_zone_id]

            found_spot = False
            random.shuffle(possible_bubble_hexes_in_zone) 

            for bubble_candidate_hex in possible_bubble_hexes_in_zone:
                if found_spot: break
                if bubble_candidate_hex.terrain not in ['plain', 'swamp']:
                    continue
                
                shuffled_pod_shapes = list(starfreighter_type.pod_shapes)
                random.shuffle(shuffled_pod_shapes)

                for pod_shape_obj in shuffled_pod_shapes:
                    chosen_pod_angles = pod_shape_obj.pod_angles
                    potential_freighter_coords = self.state.board.place_freighter(bubble_candidate_hex.col, bubble_candidate_hex.row, chosen_pod_angles)
                    if len(potential_freighter_coords) != 4:
                        continue
                
                    valid_placement = True
                    current_all_landed_hexes = {coord for landing in self.freighter_landings.values() for coord in landing['occupied_hexes']}

                    for i, (p_col, p_row) in enumerate(potential_freighter_coords):
                        hex_obj = self.state.board.get_hex(p_col, p_row)
                        if not hex_obj or hex_obj.terrain not in ['plain', 'swamp'] or (p_col, p_row) in current_all_landed_hexes:
                            valid_placement = False
                            break
                    if not valid_placement: continue
                
                    bubble_zone_id = chosen_zone_id 
                    for i, (p_col, p_row) in enumerate(potential_freighter_coords):
                        if i == 0: continue
                        pod_hex = self.state.board.get_hex(p_col, p_row)
                        if pod_hex and pod_hex.zone_id is not None and pod_hex.zone_id != bubble_zone_id:
                            valid_placement = False; break
                    if not valid_placement: continue
                    
                    for p_col, p_row in potential_freighter_coords:
                        if self.state.board.is_edge_hex(p_col, p_row):
                            valid_placement = False; break
                    if not valid_placement: continue
                    
                    self.freighter_landings[player.id] = {
                        'zone_id': chosen_zone_id,
                        'occupied_hexes': potential_freighter_coords,
                        'pod_shape_angles': chosen_pod_angles
                    }
                    self.landed_freighter_zones.add(chosen_zone_id)
                    player.freighter_landed = True
                    print(f"Success! {player.name} landed in Zone {chosen_zone_id} ... Hexes: {potential_freighter_coords}")
                    
                    hexes_in_zone_to_clear_ore = [h for h in self.state.board.hexes.values() if h.zone_id == chosen_zone_id]
                    for hex_to_clear in hexes_in_zone_to_clear_ore:
                        if hex_to_clear.ore: hex_to_clear.ore = False
                
                    self._display_board_state_matplotlib(self.state.turn_number, filename_suffix="_turn_1_landing_in_progress")
                    found_spot = True; break 
            
            if not found_spot: print(f"Critical: Could not find landing spot for {player.name}...")

    def _handle_turn_2_deployment(self) -> None:
        print("\nHandling Turn 2: Unit Deployment phase.")
        initial_units = { "barge": 1, "crab": 1, "weather_hen": 1, "gunboat": 2, "tank": 4, "heap": 1, "pontoon": 1 }
        
        for player in self.state.players:
            print(f"\n--- {player.name}'s Unit Deployment ---")
            player.initial_unit_pool = initial_units.copy()

            if not self.freighter_landings.get(player.id, {}).get('zone_id'):
                print(f"Warning: Player {player.id} has no landing zone. Cannot deploy."); continue

            landing_zone_id = self.freighter_landings[player.id]['zone_id']
            zone_hexes = self.state.board.get_hexes_in_zone(landing_zone_id)
            if not zone_hexes: print(f"Warning: No hexes in landing zone {landing_zone_id}. Cannot deploy."); continue
            
            occupied_this_turn_deployment: Set[Tuple[int, int]] = set()
            if player.id in self.freighter_landings:
                freighter_hex_coords = self.freighter_landings[player.id].get('occupied_hexes', [])
                for f_col, f_row in freighter_hex_coords: occupied_this_turn_deployment.add((f_col, f_row))

            # Clear player's unit lists before populating them based on deployment outcome
            player.units_on_board = []
            player.units_in_freighter = []

            for unit_type_id, count in player.initial_unit_pool.items():
                unit_type = self.state.unit_types_data.get(unit_type_id)
                if not unit_type: print(f"Warning: Unit type '{unit_type_id}' not found. Cannot deploy."); continue

                for _ in range(count):
                    deployed_this_instance = False
                    random.shuffle(zone_hexes)
                    for hex_candidate in zone_hexes:
                        if (hex_candidate.col, hex_candidate.row) in occupied_this_turn_deployment: continue
                        if hex_candidate.terrain not in unit_type.can_enter: continue
                        
                        primary_hex_is_coastal = False
                        if unit_type_id in ["barge", "gunboat"]:
                            neighbors = self.state.board.get_neighbors(hex_candidate)
                            if not any(n.terrain == 'sea' for n in neighbors): continue
                        
                        second_hex_coords: Optional[Tuple[int, int]] = None
                        if unit_type_id == "barge":
                            if self.state.board.is_edge_hex(hex_candidate.col, hex_candidate.row): continue
                            possible_second_hexes = self.state.board.get_neighbors(hex_candidate)
                            random.shuffle(possible_second_hexes)
                            found_second_barge_hex = False
                            for adj_hex in possible_second_hexes:
                                if self.state.board.is_edge_hex(adj_hex.col, adj_hex.row): continue
                                if (adj_hex.col, adj_hex.row) in occupied_this_turn_deployment: continue
                                valid_second_terrain = adj_hex.terrain == 'sea' or \
                                                     (adj_hex.terrain in unit_type.can_enter and adj_hex.zone_id == hex_candidate.zone_id)
                                if valid_second_terrain: second_hex_coords = (adj_hex.col, adj_hex.row); found_second_barge_hex = True; break
                            if not found_second_barge_hex: continue
                        
                        new_unit_id = uuid.uuid4().hex
                        deployed_unit = Unit(
                            unit_id=new_unit_id, unit_type_id=unit_type_id, player_id=player.id, 
                            col=hex_candidate.col, row=hex_candidate.row,
                            second_hex_col=second_hex_coords[0] if second_hex_coords else None,
                            second_hex_row=second_hex_coords[1] if second_hex_coords else None,
                            is_in_freighter=False
                        )
                        player.units_on_board.append(deployed_unit)
                        occupied_this_turn_deployment.add((hex_candidate.col, hex_candidate.row))
                        if second_hex_coords: occupied_this_turn_deployment.add(second_hex_coords)
                        # print(f"Player {player.id} deployed {unit_type_id} at ...")
                        deployed_this_instance = True; break 
                    
                    if not deployed_this_instance:
                        # print(f"Warning: Player {player.id} could not deploy {unit_type_id}. Stays in freighter.")
                        freighter_bubble_col, freighter_bubble_row = -1,-1
                        if player.id in self.freighter_landings and self.freighter_landings[player.id]['occupied_hexes']:
                            freighter_bubble_col, freighter_bubble_row = self.freighter_landings[player.id]['occupied_hexes'][0]
                        reserve_unit_id = uuid.uuid4().hex
                        unit_staying_in_freighter = Unit(
                            unit_id=reserve_unit_id, unit_type_id=unit_type_id, player_id=player.id,
                            col=freighter_bubble_col, row=freighter_bubble_row, is_in_freighter=True
                        )
                        player.units_in_freighter.append(unit_staying_in_freighter)
            
            player.initial_unit_pool.clear()
            # print(f"Player {player.id} deployment complete. Deployed: {len(player.units_on_board)}, In Freighter: {len(player.units_in_freighter)}")

    def _handle_player_actions(self, player: Player, turn_def: TurnDefinition) -> None:
        """Handle a player's actions during their turn using the command framework."""
        print(f"Player {player.id} takes actions... (New command loop logic)")

        # Ensure GameState is accessible. It should be self.state
        if not hasattr(self, 'state') or self.state is None:
            print(f"CRITICAL: GameState (self.state) not found in GameEngine for player {player.id}. Cannot handle actions.")
            return

        while player.can_still_act():
            # The player.next_command method should accept the GameState
            cmd = player.next_command(self.state) 
            
            if not cmd:
                print(f"Player {player.id}: No more commands to issue or decided to end turn.")
                break # No command given, player ends their action phase
            
            estimated_cost = cmd.estimate_ap_cost(self.state)
            print(f"Player {player.id}: Considering command {type(cmd).__name__} with estimated cost {estimated_cost} AP.")

            # Check if player can afford it using their current AP for spending
            # The spend_ap method already incorporates this check from _total_ap_for_spending_this_turn
            if player.spend_ap(estimated_cost):
                print(f"Player {player.id}: Executing command {type(cmd).__name__}.")
                cmd.execute(self.state)
                # Potentially update self.state.units_by_id if unit properties (like col/row) changed
                # For MoveCommand, unit's col/row are directly mutated, so units_by_id in GameState is fine.
            else:
                print(f"Player {player.id}: Cannot afford command {type(cmd).__name__} (cost: {estimated_cost}). Ending action phase.")
                break # Cannot afford, player ends their action phase
        
        print(f"Player {player.id} action phase concluded.")

    def _end_game_summary(self) -> None:
        print("\nGame Over. Calculating scores...")
        # Score calculation to be implemented later 

    def _get_adjacent_zone_ids(self, zone_id_str: str) -> List[str]:
        if not zone_id_str or zone_id_str in ["13", "14"]: return [] 
        try:
            zone_int = int(zone_id_str)
            if 1 <= zone_int <= 12: 
                prev_zone = str((zone_int - 2 + 12) % 12 + 1)
                next_zone = str((zone_int % 12) + 1)
                return [prev_zone, next_zone]
        except ValueError: print(f"Warning: Invalid zone_id '{zone_id_str}' for adjacency calculation.")
        return []

    # Removed _is_valid_edge_passage as its intent is replaced by the direct is_edge_hex check for landing

    # ... (rest of the class, like _display_board_state_matplotlib etc.) 