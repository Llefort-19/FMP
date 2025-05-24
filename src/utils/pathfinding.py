import heapq
from typing import List, Tuple, Callable, Dict, Any, Optional, TYPE_CHECKING

# Forward declarations for type hinting
if TYPE_CHECKING:
    from ..board import Board, Hex # Assuming Hex is in board
    from ..units import UnitType # For can_enter list
    # from ..game_state import GameState # GameState not directly used in type hints here currently

# Heuristic function (Manhattan distance for hex grid, axial distance)
def _heuristic(a_col: int, a_row: int, b_col: int, b_row: int, board: 'Board') -> int:
    """Calculates axial distance heuristic for flat-topped odd-q grids."""
    aq, ar = board._oddq_to_axial(a_col, a_row)
    bq, br = board._oddq_to_axial(b_col, b_row)
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2

def a_star_pathfinding(
    board: 'Board',
    start_coords: Tuple[int, int], 
    goal_coords: Tuple[int, int],
    unit_type: 'UnitType', # UnitType contains can_enter property
    tide_type: str
) -> Optional[List[Tuple[int, int]]]:
    """
    Finds a path from start_coords to goal_coords using A* algorithm.
    Considers effective terrain based on tide and unit's movement capabilities.
    Args:
        board: The game board instance.
        start_coords: (col, row) of the starting hex.
        goal_coords: (col, row) of the destination hex.
        unit_type: The UnitType of the moving unit (for can_enter checks).
        tide_type: Current tide ("low", "mid", "high").
    Returns:
        A list of (col, row) tuples representing the path, or None if no path is found.
    """
    start_node_col, start_node_row = start_coords
    goal_node_col, goal_node_row = goal_coords

    open_set = []
    heapq.heappush(open_set, (0, start_coords)) # (priority, item)
    
    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    
    g_score: Dict[Tuple[int, int], float] = {start_coords: 0}
    f_score: Dict[Tuple[int, int], float] = {start_coords: _heuristic(start_node_col, start_node_row, goal_node_col, goal_node_row, board)}

    while open_set:
        _, current_coords = heapq.heappop(open_set)
        current_col, current_row = current_coords

        if current_coords == goal_coords:
            path = []
            while current_coords in came_from:
                path.append(current_coords)
                current_coords = came_from[current_coords]
            path.append(start_coords) # Add the start node
            return path[::-1] # Return reversed path

        current_hex_obj = board.get_hex(current_col, current_row)
        if not current_hex_obj: # Should not happen if start is valid
            continue

        neighbors_hex_objects = board.get_neighbors(current_hex_obj)

        for neighbor_hex_obj in neighbors_hex_objects:
            neighbor_coords = (neighbor_hex_obj.col, neighbor_hex_obj.row)
            
            effective_terrain = board.effective_terrain(neighbor_hex_obj, tide_type)
            if effective_terrain not in unit_type.can_enter:
                continue # Unit cannot enter this terrain type
            
            # Assuming cost to move to any valid neighbor is 1
            tentative_g_score = g_score[current_coords] + 1 

            if tentative_g_score < g_score.get(neighbor_coords, float('inf')):
                came_from[neighbor_coords] = current_coords
                g_score[neighbor_coords] = tentative_g_score
                f_score[neighbor_coords] = tentative_g_score + _heuristic(neighbor_hex_obj.col, neighbor_hex_obj.row, goal_node_col, goal_node_row, board)
                if not any(item[1] == neighbor_coords for item in open_set):
                    heapq.heappush(open_set, (f_score[neighbor_coords], neighbor_coords))

    return None # No path found 