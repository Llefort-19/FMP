from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import random

@dataclass
class TideCard:
    id: str
    type: str  # e.g., "low", "normal", "high"
    name: str

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TideCard):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

class TideDeck:
    def __init__(self, tide_data: Dict[str, Any]):
        self.all_cards_definitions: List[TideCard] = [
            TideCard(**card_def) for card_def in tide_data.get('tide_cards', [])
        ]
        self.setup_rules: Dict[str, Any] = tide_data.get('setup', {})
        self.fixed_turns: Dict[str, str] = tide_data.get('fixed_turns', {}) # e.g., {"1": "normal", "2": "normal"}
        self.reshuffle_rules: Dict[str, Any] = tide_data.get('reshuffle', {})

        self.future_deck: List[TideCard] = []
        self.reserve_pile: List[TideCard] = []
        self.discard_pile: List[TideCard] = []
        self.current_tide_card: Optional[TideCard] = None
        
        # Basic validation for total cards if definitions are present
        if self.all_cards_definitions and len(self.all_cards_definitions) != 15:
            print(f"Warning: Expected 15 tide card definitions, but found {len(self.all_cards_definitions)}.")

        print("TideDeck initialized.")

    def _find_card_by_type(self, card_type: str) -> Optional[TideCard]:
        """Helper to find the first card definition of a given type."""
        for card in self.all_cards_definitions:
            if card.type == card_type:
                return card
        return None

    def setup_deck_for_play(self) -> None:
        """Sets up the deck for play, typically at the start of Turn 3."""
        if not self.all_cards_definitions:
            print("Error: No card definitions to set up deck.")
            return

        shuffled_cards = list(self.all_cards_definitions)
        random.shuffle(shuffled_cards)

        future_deck_size = self.setup_rules.get('future_deck_size', 9)
        # reserve_size_config = self.setup_rules.get('reserve_size', 6) # Not directly used if we prioritize future_deck_size

        if future_deck_size > len(shuffled_cards):
            future_deck_size = len(shuffled_cards)
            print(f"Warning: future_deck_size ({self.setup_rules.get('future_deck_size', 9)}) exceeds available cards. Adjusting to {future_deck_size}.")

        self.future_deck = shuffled_cards[:future_deck_size]
        self.reserve_pile = shuffled_cards[future_deck_size:]
        self.discard_pile = [] # Ensure discard is clear at setup

        print(f"Tide deck set up for play: Future {len(self.future_deck)}, Reserve {len(self.reserve_pile)}")

    def get_tide_for_turn(self, turn_number: int) -> Optional[TideCard]:
        turn_str = str(turn_number)
        if turn_str in self.fixed_turns:
            tide_type = self.fixed_turns[turn_str]
            # For fixed turns, we provide a card of the type but don't draw it from any deck.
            # It's a representation of the tide, not a consumed card object from the play piles.
            fixed_tide_card = self._find_card_by_type(tide_type)
            if not fixed_tide_card:
                 print(f"Error: Could not find a '{tide_type}' card in definitions for fixed turn {turn_number}.")
            return fixed_tide_card
        else:
            if not self.future_deck:
                # This case should ideally be handled by reshuffle logic or game end
                print(f"ERROR: get_tide_for_turn (Turn {turn_number}): Future deck is empty when trying to draw.")
                return None
            return self.future_deck.pop(0)

    def advance_turn_tide(self, turn_number: int) -> None:
        setup_deck_turn = self.setup_rules.get('setup_deck_turn', 3)
        last_fixed_turn = self.setup_rules.get('last_fixed_turn', 2)

        # 1. Initial Deck Setup (if applicable)
        # If it's the turn to set up the deck, and the future deck hasn't been populated yet.
        if turn_number == setup_deck_turn and not self.future_deck:
            print(f"INFO: Turn {turn_number}: Performing initial deck setup as future_deck is empty.")
            self.setup_deck_for_play()

        # 2. Discard previous turn's card (if it was a drawn card)
        # self.current_tide_card currently holds the card from the *previous* turn (turn_number - 1)
        previous_turn_for_card = turn_number - 1
        if self.current_tide_card is not None:
            if previous_turn_for_card > last_fixed_turn:
                print(f"INFO: Turn {turn_number}: Discarding card '{self.current_tide_card.name}' from previous turn {previous_turn_for_card}.")
                self.discard_pile.append(self.current_tide_card)
            else:
                # This case handles fixed turn cards (e.g. card from turn 1 or 2 not being discarded when processing turn 2 or 3 respectively)
                print(f"INFO: Turn {turn_number}: Card '{self.current_tide_card.name}' from previous fixed turn {previous_turn_for_card} (or turn 0 if turn_number is 1) not discarded.")
        
        # 3. Draw new card for the current turn
        # print(f"INFO: Turn {turn_number}: Attempting to draw new tide card.") # Already part of get_tide_for_turn or implied
        new_card = self.get_tide_for_turn(turn_number) # This might pop from future_deck
        self.current_tide_card = new_card
        if self.current_tide_card:
            print(f"INFO: Turn {turn_number}: Current tide card is now '{self.current_tide_card.name}'.")
        else:
            # This is an error if turn_number >= setup_deck_turn and no reshuffle/reserve fixed it before this point.
            # get_tide_for_turn would have already printed an error if future_deck was empty for a draw turn.
            print(f"INFO: Turn {turn_number}: No new tide card drawn (e.g. fixed turn without card, or deck truly empty after attempts to fill future_deck).")

        # 4. Reshuffle checks & drawing from reserve (only active from setup turn onwards)
        if turn_number >= setup_deck_turn: 
            reshuffle_trigger_turns = self.reshuffle_rules.get('turns', [])
            
            # Check for turn-based reshuffle first.
            if turn_number in reshuffle_trigger_turns:
                print(f"INFO: Turn {turn_number}: Triggering reshuffle as per rules.")
                self.reshuffle() 
            
            # If, after potential reshuffle (or if no reshuffle this turn), 
            # the future_deck is empty (e.g. card drawn in step 3 emptied it), 
            # AND there are cards in reserve, move one to future_deck.
            # This also covers the case where the initial setup_deck_for_play didn't fill future_deck completely due to few definitions.
            if not self.future_deck and self.reserve_pile:
                print(f"INFO: Turn {turn_number}: Future deck empty after draw/reshuffle, drawing from reserve pile.")
                self.future_deck.append(self.reserve_pile.pop(0))
                print(f"INFO: Moved 1 card from reserve to future. Future: {len(self.future_deck)}, Reserve: {len(self.reserve_pile)}")

    def reshuffle(self) -> None:
        """Shuffle all 15 cards except the CURRENT one, stack 9 as new Future deck, set 6 aside."""
        if not self.all_cards_definitions:
            print("Error: No card definitions available for reshuffle.")
            return
        
        cards_to_shuffle = list(self.all_cards_definitions)
        if self.current_tide_card:
            try:
                # Ensure we remove the exact instance if it came from definitions, or by ID.
                # Using ID for robustness as current_tide_card might be a copy or different instance.
                current_card_id_to_exclude = self.current_tide_card.id
                cards_to_shuffle = [card for card in cards_to_shuffle if card.id != current_card_id_to_exclude]
            except AttributeError:
                 print("Warning: current_tide_card has no id for reshuffle exclusion, shuffling all cards.")

        if len(cards_to_shuffle) != (len(self.all_cards_definitions) - (1 if self.current_tide_card else 0)):
            if self.current_tide_card:
                 print(f"Warning: Expected {len(self.all_cards_definitions) - 1} cards for reshuffle (excluding current), but got {len(cards_to_shuffle)}. Check current card ID matching.")
            # Proceeding with what we have

        random.shuffle(cards_to_shuffle)

        future_deck_size = self.setup_rules.get('future_deck_size', 9)
        # reserve_expected = self.setup_rules.get('reserve_size_after_reshuffle', 5) # if 14 cards are shuffled
        
        if future_deck_size > len(cards_to_shuffle):
            future_deck_size = len(cards_to_shuffle)
            print(f"Warning: reshuffle future_deck_size ({self.setup_rules.get('future_deck_size', 9)}) exceeds available cards. Adjusting to {future_deck_size}.")

        self.future_deck = cards_to_shuffle[:future_deck_size]
        self.reserve_pile = cards_to_shuffle[future_deck_size:]
        self.discard_pile = []  # Clear discard pile on reshuffle

        print(f"Reshuffled. Current card ('{self.current_tide_card.name if self.current_tide_card else 'None'}') was kept. Future: {len(self.future_deck)}, Reserve: {len(self.reserve_pile)}, Discard: {len(self.discard_pile)}")

    def get_next_tide_card_to_draw(self) -> Optional[TideCard]:
        if self.future_deck:
            return self.future_deck[0]
        return None

    def get_next_two_tide_cards_to_draw(self) -> List[TideCard]:
        return self.future_deck[:2] 