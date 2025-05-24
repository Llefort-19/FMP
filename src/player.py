from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING

# Forward declarations for type hinting
if TYPE_CHECKING:
    from .game_state import GameState
    from .commands import GameCommand

MAX_BANKED_AP = 10 # Max AP that can be in the bank (saved)
REGULAR_TURN_BASE_AP = 15

@dataclass
class Player:
    id: str
    name: str
    color: str
    
    # AP for the current turn, derived solely from the turn definition
    current_turn_base_ap: int = 0 
    # AP spent during the current turn (from base or banked)
    action_points_spent_this_turn: int = 0 
    # Persistent pool of saved AP
    action_points_banked: int = 0 
    
    # Transient variables for current turn calculations
    _banked_ap_at_start_of_actions: int = field(init=False, default=0, repr=False)
    _total_ap_for_spending_this_turn: int = field(init=False, default=0, repr=False)

    freighter_landed: bool = False
    ore_in_freighter: int = 0
    
    units_on_board: List[Any] = field(default_factory=list) 
    units_in_freighter: List[Any] = field(default_factory=list)
    initial_unit_pool: Dict[str, int] = field(default_factory=dict)
    
    has_weather_hen_operational: bool = False

    def get_total_available_ap(self) -> int:
        """Total AP player can currently spend (base for current turn + banked)."""
        return self.current_turn_base_ap + self.action_points_banked

    def prepare_for_new_turn(self, base_ap_from_turn_definition: int) -> None:
        """Called at the start of a player's turn."""
        self.current_turn_base_ap = base_ap_from_turn_definition
        self.action_points_spent_this_turn = 0
        
        # Store bank state at start of this player's actions for end-of-turn calculation
        self._banked_ap_at_start_of_actions = self.action_points_banked 
        self._total_ap_for_spending_this_turn = self.current_turn_base_ap + self._banked_ap_at_start_of_actions
        
        print(f"Player {self.id}: Prepared for new turn. Base AP: {self.current_turn_base_ap}, "
              f"Initial Banked AP: {self._banked_ap_at_start_of_actions}. "
              f"Total Available for spending: {self._total_ap_for_spending_this_turn}")

    def can_spend_ap(self, cost: int) -> bool:
        """Checks if the player has enough AP to spend from their total pool for the turn."""
        return (self._total_ap_for_spending_this_turn - self.action_points_spent_this_turn) >= cost

    def spend_ap(self, cost: int) -> bool:
        """Attempts to spend AP. Returns True if successful, False otherwise."""
        if not self.can_spend_ap(cost):
            available_ap_now = self._total_ap_for_spending_this_turn - self.action_points_spent_this_turn
            print(f"Warning: Player {self.id} cannot spend {cost} AP. Available now: {available_ap_now}. Needed: {cost}.")
            return False

        self.action_points_spent_this_turn += cost
        print(f"Player {self.id} spent {cost} AP. Total spent this turn: {self.action_points_spent_this_turn}. "
              f"Remaining from turn pool: {self._total_ap_for_spending_this_turn - self.action_points_spent_this_turn}")
        return True

    def end_turn_banking_ap(self) -> None:
        """Calculates AP to bank based on unspent AP from the total turn pool."""
        unspent_ap_from_total_pool = self._total_ap_for_spending_this_turn - self.action_points_spent_this_turn
        
        newly_banked_this_round = 0
        if unspent_ap_from_total_pool >= 10:
            newly_banked_this_round = 10
        elif unspent_ap_from_total_pool >= 5:
            newly_banked_this_round = 5
        # Else, newly_banked_this_round remains 0

        # The amount of AP banked is directly determined by the unspent AP criteria.
        self.action_points_banked = min(newly_banked_this_round, MAX_BANKED_AP)
        
        print(f"Player {self.id} ended turn. Total AP available for spending: {self._total_ap_for_spending_this_turn}. "
              f"AP Spent: {self.action_points_spent_this_turn}. Unspent from pool: {unspent_ap_from_total_pool}. "
              f"Newly Banked this round: {newly_banked_this_round}. Final Banked AP: {self.action_points_banked}.")

    # Methods for Task 7 (GameEngine._handle_player_actions)
    def can_still_act(self) -> bool:
        """Checks if the player can still perform actions (e.g., has AP or units to command)."""
        # For now, let's assume player can act if they have some AP left in their current spending pool.
        # More sophisticated logic could check for available commands, unit states, etc.
        available_ap_now = self._total_ap_for_spending_this_turn - self.action_points_spent_this_turn
        return available_ap_now > 0

    def next_command(self, state: 'GameState') -> Optional['GameCommand']:
        """Determines the next command the player wants to issue. Stub for now."""
        # This would involve player input or AI logic.
        # For Phase 1, returning None is sufficient as per spec.
        print(f"Player {self.id}: next_command() called, returning None (stub).")
        return None 