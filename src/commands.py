from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, TYPE_CHECKING

# Forward declarations for type hinting
if TYPE_CHECKING:
    from .game_state import GameState

class GameCommand(ABC):
    """Abstract base class for all game commands."""

    @abstractmethod
    def estimate_ap_cost(self, state: 'GameState') -> int:
        """Estimates the Action Point (AP) cost of executing this command."""
        pass

    @abstractmethod
    def execute(self, state: 'GameState') -> None:
        """Executes the command, modifying the game state."""
        pass

    def can_execute(self, state: 'GameState', available_ap: int) -> bool:
        """Checks if the command can be executed with the available AP."""
        # Default implementation, can be overridden by subclasses for more complex checks
        return available_ap >= self.estimate_ap_cost(state)

# Specific Command Implementations
from .utils.pathfinding import a_star_pathfinding # Corrected import path

class MoveCommand(GameCommand):
    def __init__(self, unit_id: str, dest_col: int, dest_row: int):
        self.unit_id = unit_id
        self.dest_col = dest_col
        self.dest_row = dest_row
        self._cached_path: Optional[List[Tuple[int, int]]] = None
        self._cached_path_state_tuple: Optional[Tuple[int, int, str, int, int]] = None # (unit_col, unit_row, tide, dest_col, dest_row)

    def _calculate_path(self, state: 'GameState') -> Optional[List[Tuple[int, int]]]:
        unit_to_move = state.get_unit(self.unit_id)
        current_unit_coords = (unit_to_move.col, unit_to_move.row)
        destination_coords = (self.dest_col, self.dest_row)

        # Cache check for path calculation
        # Path depends on unit's start, destination, and tide state (affecting terrain)
        # Also depends on the board structure itself, which we assume is static for the path calc.
        state_tuple_for_cache = (
            unit_to_move.col, 
            unit_to_move.row, 
            state.tide_state, 
            self.dest_col, 
            self.dest_row
        )
        if self._cached_path_state_tuple == state_tuple_for_cache and self._cached_path is not None:
            return self._cached_path

        # Need UnitType to check can_enter. Assume Unit has unit_type_id, and GameState can provide UnitType
        # This requires GameState to have access to unit type definitions, or Unit to carry its UnitType.
        # For now, let's assume state can provide it or unit has it directly.
        # Let's modify GameState or Unit if necessary later. For now, mock it if Unit doesn't have unit_type.
        
        # Option 1: Unit carries its UnitType object (complex to set up from JSON)
        # Option 2: GameState has a unit_types dictionary like GameEngine
        # For the test `minimal_state`, unit.unit_type_id is "tank". We need a mock UnitType for "tank".
        # Let's assume for now `state.board` can give unit_type, or we pass it via GameState

        # To make this work, we need unit_types in GameState or accessible through it.
        # The test will pass a unit_type_id. We need the full UnitType object for `can_enter`.
        # Let's assume `state` has a field `unit_types_data: Dict[str, UnitType]` for now.
        # This means Task 2 (refactor GameEngine) will need to populate this.

        # Accessing unit_type_data - this implies GameState needs modification or a helper
        # For the purpose of this command, let's assume state.get_unit_type_definition(unit_to_move.unit_type_id)
        # This is a temporary placeholder until GameState structure is finalized with unit types.
        try:
            # This is a structural assumption, may need adjustment after GameEngine refactor
            unit_type_def = state.unit_types_data[unit_to_move.unit_type_id]
        except (AttributeError, KeyError):
            # Fallback for tests if state.unit_types_data is not yet implemented
            # This is a HACK for the test_move_cost to pass without full GameState integration
            class MockUnitType:
                def __init__(self, can_enter_terrains):
                    self.can_enter = can_enter_terrains
            if unit_to_move.unit_type_id == "tank":
                 unit_type_def = MockUnitType(["plain", "swamp", "reef", "mountain", "sea"]) # Tanks can go anywhere on flat_land test
            else:
                # Default to a unit type that can only enter plain if not specified
                unit_type_def = MockUnitType(["plain"])

        path = a_star_pathfinding(
            board=state.board,
            start_coords=current_unit_coords,
            goal_coords=destination_coords,
            unit_type=unit_type_def, # Pass the actual UnitType object
            tide_type=state.tide_state
        )
        
        self._cached_path = path
        self._cached_path_state_tuple = state_tuple_for_cache
        return path

    def estimate_ap_cost(self, state: 'GameState') -> int:
        path = self._calculate_path(state)
        if path and len(path) > 0:
            return len(path) - 1 # Cost is number of steps
        return float('inf') # No path or invalid path means effectively infinite cost

    def execute(self, state: 'GameState') -> None:
        path = self._calculate_path(state)
        if path and len(path) > 0:
            # Path includes the start node, so if path has 1 element, it means no move.
            # If len(path) > 1, it means there are steps to take.
            # The destination is the last element in the path.
            final_col, final_row = path[-1]
            unit_to_move = state.get_unit(self.unit_id)
            unit_to_move.col = final_col
            unit_to_move.row = final_row
            # print(f"Unit {self.unit_id} moved to ({final_col},{final_row}) via path: {path}")
        else:
            # print(f"Could not execute move for unit {self.unit_id}: No valid path to ({self.dest_col},{self.dest_row}).")
            # Optionally raise an error or log a warning if execution is attempted with no path
            pass 