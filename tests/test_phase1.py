import pytest
from typing import Tuple, Dict, List # Added for type hints

# Assuming src is in PYTHONPATH or tests are run from project root
from src.game_state import GameState
from src.board import Board, Hex # Assuming Hex is in board
from src.units import Unit, UnitType # Assuming UnitType is in units for tests
from src.commands import MoveCommand
from src.player import Player # Added for GameState players list

# Helper to create a simple board for testing
def create_test_board(cols: int = 5, rows: int = 5, default_terrain: str = "plain") -> Board:
    """Creates a board with specified dimensions and default terrain."""
    board = Board(map_file_path=None) # Initialize with no file to avoid loading default map
    board.hexes = {}
    for r in range(rows):
        for c in range(cols):
            hex_obj = Hex(col=c, row=r, terrain=default_terrain)
            board.hexes[(c, r)] = hex_obj
    board._calculate_bounds() # Important for board utility functions
    return board

# Minimal state for testing
def minimal_state_setup() -> Tuple[GameState, Unit]:
    board = create_test_board(5, 5, "plain")
    # Mock UnitType for "tank" for pathfinding in MoveCommand
    # This aligns with the hack in MoveCommand._calculate_path
    tank_type = UnitType(
        id="tank", name="Tank", category="ground", category_type="vehicle", 
        can_enter=["plain", "swamp", "reef", "mountain", "sea"], # Allows movement on test plain board
        tide_sensitive=False
    )
    unit_types_for_state = {"tank": tank_type}

    # For test_tide_neutralises_boat, we need an "attack_boat" type.
    attack_boat_type = UnitType(
        id="attack_boat", name="Attack Boat", category="naval", category_type="boat",
        can_enter=["sea"], # Normally sea only
        tide_sensitive=True # Boats are usually tide sensitive
    )
    unit_types_for_state["attack_boat"] = attack_boat_type

    unit = Unit(unit_id="u1", unit_type_id="tank", player_id="P1", col=0, row=0)
    players_list: List[Player] = [Player(id="P1", name="Player 1", color="red")]
    
    state = GameState(
        board=board, 
        tide_state="mid", 
        units_by_id={"u1": unit}, 
        players=players_list, 
        unit_types_data=unit_types_for_state, # Provide mock unit types
        turn_number=1
    )
    return state, unit

def test_move_cost():
    state, _ = minimal_state_setup()
    # Moving from (0,0) to (0,3) on a 5x5 plain board. Path length = 4. Cost = 3.
    cmd = MoveCommand(unit_id="u1", dest_col=0, dest_row=3)
    assert cmd.estimate_ap_cost(state) == 3

def test_move_exec():
    state, unit = minimal_state_setup()
    cmd = MoveCommand(unit_id="u1", dest_col=0, dest_row=2)
    cmd.execute(state) # Path (0,0)->(0,1)->(0,2)
    assert (unit.col, unit.row) == (0, 2)

def test_tide_neutralises_boat():
    board = create_test_board(5, 5, "plain")
    # Modify specific hex for the test
    swamp_hex = board.get_hex(0,0)
    if swamp_hex: swamp_hex.terrain = "swamp"
    
    # Get the mock attack_boat_type defined in minimal_state_setup helper
    # This requires unit_types_data to be part of the GameState used here.
    attack_boat_type = UnitType(
        id="attack_boat", name="Attack Boat", category="naval", category_type="boat",
        can_enter=["sea"], tide_sensitive=True
    )
    mock_unit_types = {"attack_boat": attack_boat_type}

    boat = Unit(unit_id="b1", unit_type_id="attack_boat", player_id="P1", col=0, row=0)
    # Ensure the unit has the is_neutralised attribute, added in units.py earlier
    assert hasattr(boat, 'is_neutralised'), "Unit class missing 'is_neutralised' attribute"
    boat.is_neutralised = False # Explicitly set to False before test

    state = GameState(
        board=board, 
        tide_state="high", # Test condition: high tide
        units_by_id={"b1": boat}, 
        players=[Player(id="P1", name="Test Player", color="blue")],
        unit_types_data=mock_unit_types,
        turn_number=1
    )
    
    # Board.apply_tide_effects should use state (including tide_state and units) to set is_neutralised
    state.board.apply_tide_effects(state)
    assert boat.is_neutralised is True, \
        f"Boat on {swamp_hex.terrain if swamp_hex else 'N/A'} at high tide (eff: {state.board.effective_terrain(swamp_hex, state.tide_state) if swamp_hex else 'N/A'}) should be neutralised per test spec" 