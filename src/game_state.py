from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

# Forward declarations for type hinting
if TYPE_CHECKING:
    from .board import Board
    from .units import Unit, UnitType
    from .player import Player

@dataclass
class GameState:
    board: 'Board'
    tide_state: str  # "low" / "mid" / "high"
    units_by_id: Dict[str, 'Unit']
    players: List['Player']
    unit_types_data: Dict[str, 'UnitType']
    turn_number: int = 1
    # Potentially add current_player_index or current_player_id later

    def get_unit(self, unit_id: str) -> 'Unit':
        """Retrieves a unit by its ID, asserting its presence."""
        unit = self.units_by_id.get(unit_id)
        assert unit is not None, f"Unit with ID '{unit_id}' not found in game state."
        return unit

    # Example of how one might initialize it later (not part of this task, just for context)
    # @classmethod
    # def initialize_from_engine(cls, engine: 'GameEngine'): # Assuming GameEngine is accessible
    #     return cls(
    #         board=engine.board,
    #         tide_state="mid", # Or get from engine.tide_deck.current_tide.type or similar
    #         units_by_id={u.unit_id: u for p in engine.players for u in p.units_on_board + p.units_in_freighter},
    #         players=engine.players,
    #         turn_number=engine.turn_manager.current_turn_number if engine.turn_manager else 1
    #     ) 