from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple # Tuple included as per spec

@dataclass
class UnitTurret:
    count: int
    range: int

@dataclass
class UnitPodShape:
    shape_id: str
    pod_angles: List[int]  # List of angles in degrees for each pod relative to bubble

@dataclass
class RangeModifier:
    terrain: str
    range: int

@dataclass
class UnitType:
    id: str
    name: str
    category: str
    category_type: str
    can_enter: List[str]
    tide_sensitive: bool
    # Optional fields with defaults
    pod_shapes: Optional[List[UnitPodShape]] = None
    footprint: Optional[List[List[List[int]]]] = None # e.g., list of shapes, each shape is list of coords, each coord is [q,r]
    turrets: Optional[UnitTurret] = None
    cargo_slots: int = 0
    indestructible: bool = False
    range: Optional[int] = None
    range_modifiers: List[RangeModifier] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnitType':
        """Creates a UnitType instance from a dictionary (e.g., from JSON data)."""
        
        # Prepare arguments for the constructor, starting with assumed mandatory ones
        # based on the dataclass definition (those without defaults).
        init_kwargs = {
            'id': data['id'],
            'name': data['name'],
            'category': data['category'],
            'category_type': data['category_type'],
            'can_enter': data['can_enter'],
            'tide_sensitive': data['tide_sensitive'],
        }

        # Handle optional fields and nested structures.
        # If a key is present in `data`, its value is used for `init_kwargs`.
        # If a key is absent, the dataclass default for that field will apply upon instantiation.

        # pod_shapes: Optional[List[UnitPodShape]] = None
        pod_shapes_data = data.get('pod_shapes')
        if pod_shapes_data is not None:
            init_kwargs['pod_shapes'] = [UnitPodShape(**ps_data) for ps_data in pod_shapes_data]
        
        # footprint: Optional[List[List[List[int]]]] = None
        if 'footprint' in data: # Includes if data['footprint'] is None
            init_kwargs['footprint'] = data['footprint']

        # turrets: Optional[UnitTurret] = None
        turret_data = data.get('turrets')
        if turret_data is not None:
            init_kwargs['turrets'] = UnitTurret(**turret_data)
        
        # cargo_slots: int = 0
        if 'cargo_slots' in data:
            init_kwargs['cargo_slots'] = data['cargo_slots']

        # indestructible: bool = False
        if 'indestructible' in data:
            init_kwargs['indestructible'] = data['indestructible']

        # range: Optional[int] = None
        if 'range' in data: # Includes if data['range'] is None
            init_kwargs['range'] = data['range']

        # range_modifiers: List[RangeModifier] = field(default_factory=list)
        range_modifiers_data = data.get('range_modifiers')
        if range_modifiers_data is not None:
            init_kwargs['range_modifiers'] = [RangeModifier(**rm_data) for rm_data in range_modifiers_data]
        # If range_modifiers_data is None (key missing or JSON null), 
        # 'range_modifiers' is not added to init_kwargs, so default_factory=list is used.
        
        return cls(**init_kwargs) 

@dataclass
class Unit:
    """Represents a single instance of a unit on the board or in a freighter."""
    unit_id: str  # Unique ID for this instance (e.g., generated with uuid)
    unit_type_id: str  # ID of the UnitType (e.g., "tank", "barge")
    player_id: str # ID of the owning player
    col: int
    row: int
    second_hex_col: Optional[int] = None # For multi-hex units like barge
    second_hex_row: Optional[int] = None # For multi-hex units like barge
    cargo: List['Unit'] = field(default_factory=list) # For units carried by this unit
    is_in_freighter: bool = False # True if the unit is in the freighter, False if deployed on board
    # Potentially add health, status effects, etc. later

    def __repr__(self):
        loc_repr = f"({self.col},{self.row})"
        if self.second_hex_col is not None and self.second_hex_row is not None:
            loc_repr += f" & ({self.second_hex_col},{self.second_hex_row})"
        return f"Unit(id={self.unit_id[:6]}, type={self.unit_type_id}, player={self.player_id}, loc={loc_repr}, cargo={len(self.cargo)}, in_freighter={self.is_in_freighter})" 