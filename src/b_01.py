from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

# Cube coordinate directions for even-q offset grid
# Each direction is represented as (x, y, z) where x + y + z = 0
HEX_DIR_CUBE = {
    0: (1, 0, -1),    # East
    60: (0, 1, -1),   # Northeast
    120: (-1, 1, 0),  # Northwest
    180: (-1, 0, 1),  # West
    240: (0, -1, 1),  # Southwest
    300: (1, -1, 0)   # Southeast
}

def axial_to_cube(q: int, r: int) -> tuple[int, int, int]:
    # odd-q vertical-offset: r − (q-1)//2
    x = q
    z = r - ((q - (q & 1)) // 2)
    y = -x - z
    return x, y, z

def cube_to_axial(x: int, y: int, z: int) -> tuple[int, int]:
    q = x
    r = z + ((x - (x & 1)) // 2)
    return q, r

@dataclass
class Hex:
    q: int
    r: int
    terrain: str
    ore: bool
    zone_id: Optional[int]
    pixel_x: float
    pixel_y: float
    half_hex: bool

    def __hash__(self) -> int:
        return hash((self.q, self.r))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Hex):
            return NotImplemented
        return (self.q, self.r) == (other.q, other.r)

class Board:
    def __init__(self, board_data: Dict[str, Any]):
        self.hexes: Dict[Tuple[int, int], Hex] = {}
        self.zones: Dict[str, List[Tuple[int, int]]] = {}

        hex_list_data: List[Dict[str, Any]] = board_data.get('hexes', [])
        zone_map_data: Dict[str, List[List[int]]] = board_data.get('zones', {})

        self._load_hexes(hex_list_data)
        self._load_zones(zone_map_data)

        print(f"Board initialized with {len(self.hexes)} hexes and {len(self.zones)} zones.")

    def _load_hexes(self, hex_list_data: List[Dict[str, Any]]) -> None:
        for hex_data in hex_list_data:
            if hex_data.get('half_hex') is True:
                continue

            # Ensure correct types from JSON data before creating Hex object
            # zone_id will be None if missing or if json value is null
            # other fields are assumed to be present if not half_hex
            try:
                q_val = int(hex_data['q'])
                r_val = int(hex_data['r'])
                
                hex_obj = Hex(
                    q=q_val,
                    r=r_val,
                    terrain=str(hex_data['terrain']),
                    ore=bool(hex_data['ore']),
                    zone_id=hex_data.get('zone_id'), # Handles null from JSON as None
                    pixel_x=float(hex_data['pixel_x']),
                    pixel_y=float(hex_data['pixel_y']),
                    half_hex=bool(hex_data['half_hex']) # Will be False here due to the earlier check
                )
                self.hexes[(hex_obj.q, hex_obj.r)] = hex_obj
            except KeyError as e:
                print(f"Warning: Missing expected key {e} in hex data: {hex_data}. Skipping this hex.")
            except ValueError as e:
                print(f"Warning: Type conversion error for hex data ({e}): {hex_data}. Skipping this hex.")

    def _load_zones(self, zone_map_data: Dict[str, List[List[int]]]) -> None:
        for zone_id_str, qr_pair_list in zone_map_data.items():
            self.zones[zone_id_str] = []
            for qr_pair in qr_pair_list:
                if isinstance(qr_pair, list) and len(qr_pair) == 2:
                    try:
                        q = int(qr_pair[0])
                        r = int(qr_pair[1])
                        self.zones[zone_id_str].append((q, r))
                    except ValueError:
                        print(f"Warning: Could not convert q, r to int in zone {zone_id_str} for pair {qr_pair}. Skipping.")
                else:
                    print(f"Warning: Malformed coordinate pair in zone {zone_id_str}: {qr_pair}. Skipping.")

    def get_hex(self, q: int, r: int) -> Optional[Hex]:
        return self.hexes.get((q, r))

    def get_hexes_in_zone(self, zone_id_str: str) -> List[Hex]:
        coords_in_zone: List[Tuple[int, int]] = self.zones.get(zone_id_str, [])
        hex_objects_in_zone: List[Hex] = []
        for q, r in coords_in_zone:
            hex_obj = self.get_hex(q, r)
            if hex_obj:  # Filter out None results (e.g., if coord referred to a half-hex)
                hex_objects_in_zone.append(hex_obj)
        return hex_objects_in_zone

    def place_freighter(self, bubble_q: int, bubble_r: int, pod_angles: list[int]) -> list[tuple[int, int]]:
        """
        Return [(q,r) bubble, pod1, pod2, pod3] for the given angles.
        Angles: 0°=E, 60°=NE, 120°=NW, 180°=W, 240°=SW, 300°=SE
        """
        ANGLE_TO_INDEX = {0:0, 60:1, 120:2, 180:3, 240:4, 300:5}

        EVEN_Q_OFFSETS = [  # q is even
            (+1,  0),   # 0°  E
            ( 0, -1),   # 60° NE
            (-1, -1),   # 120° NW
            (-1,  0),   # 180° W
            (-1, +1),   # 240° SW
            ( 0, +1)    # 300° SE
        ]
        ODD_Q_OFFSETS  = [  # q is odd
            (+1,  0),   # 0°  E
            (+1, -1),   # 60° NE
            ( 0, -1),   # 120° NW
            (-1,  0),   # 180° W
            ( 0, +1),   # 240° SW
            (+1, +1)    # 300° SE
        ]

        cells = [(bubble_q, bubble_r)]
        offsets = EVEN_Q_OFFSETS if bubble_q % 2 == 0 else ODD_Q_OFFSETS

        for ang in pod_angles:
            idx = ANGLE_TO_INDEX[ang]
            dq, dr = offsets[idx]
            cells.append((bubble_q + dq, bubble_r + dr))

        return cells 