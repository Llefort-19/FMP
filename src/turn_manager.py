from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class TurnDefinition:
    number: int
    name: str
    action_points: int
    special: Optional[str] = None
    tide_reshuffle: bool = False # Handles cases where key might be missing in JSON

class TurnManager:
    def __init__(self, turns_data: Dict[str, Any]):
        self.turn_definitions: Dict[int, TurnDefinition] = {}
        raw_turn_list: List[Dict[str, Any]] = turns_data.get('turns', [])
        
        for turn_dict in raw_turn_list:
            # Ensure 'number' key exists before trying to use it as a dictionary key
            if 'number' not in turn_dict:
                print(f"Warning: Turn definition missing 'number' field: {turn_dict}. Skipping.")
                continue
            try:
                # Unpack the dictionary into the dataclass constructor.
                # If 'special' or 'tide_reshuffle' are missing from turn_dict,
                # their defaults in TurnDefinition will be used.
                turn_def = TurnDefinition(**turn_dict)
                self.turn_definitions[turn_def.number] = turn_def
            except TypeError as e:
                # This might happen if turn_dict contains unexpected keys not in TurnDefinition
                # or if a required field (like name, action_points) is missing and has no default.
                print(f"Warning: Error creating TurnDefinition from dict {turn_dict} (Number: {turn_dict.get('number')}): {e}. Skipping.")
            except Exception as e:
                print(f"Warning: An unexpected error occurred processing turn definition {turn_dict.get('number')}: {e}. Skipping.")

        self.current_turn_number: int = 0
        print(f"TurnManager initialized with {len(self.turn_definitions)} turn definitions.")

    def advance_turn(self) -> Optional[TurnDefinition]:
        """Advances the game to the next turn and returns its definition."""
        self.current_turn_number += 1
        return self.get_current_turn_definition()

    def get_turn_definition(self, turn_number: int) -> Optional[TurnDefinition]:
        """Returns the TurnDefinition for a specific turn number, or None if not found."""
        return self.turn_definitions.get(turn_number)

    def get_current_turn_definition(self) -> Optional[TurnDefinition]:
        """Returns the TurnDefinition for the current turn number."""
        return self.get_turn_definition(self.current_turn_number) 