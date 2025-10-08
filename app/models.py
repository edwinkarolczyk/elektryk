from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
import uuid, time

def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

def ts() -> int:
    return int(time.time())

ElementType = str  # GNIAZDKO/LAMPA/ROLETY/WLACZNIK/ROZDZIELNICA

@dataclass
class Element:
    id: str
    etype: ElementType
    name: str
    x: int = 50
    y: int = 50
    room: Optional[str] = None
    notes: str = ""
    circuit_id: Optional[str] = None

@dataclass
class Circuit:
    id: str
    name: str          # np. O1 Gniazda
    breaker: str       # B16/B10/C20
    rcd: Optional[str] = None
    color: str = "#000000"
    enabled: bool = True
    load_va: int = 0

# 👉 NOWE: moduł na szynie DIN (w widoku rozdzielnicy)
@dataclass
class Module:
    id: str
    kind: str          # 'MAIN','MCB','RCD','RCBO','SPD','BLANK'
    label: str         # np. "B16", "30mA", "FR", "SPD"
    poles: int = 1     # szerokość (moduły 18mm) — 1,2,3,4
    row: int = 0       # wiersz (0..rows-1)
    col: int = 0       # kolumna startowa
    color: str = "#cccccc"
    circuit_id: Optional[str] = None   # powiązanie z Circuit (opcjonalnie)

@dataclass
class Board:
    id: str
    name: str
    location: str = "Rozdzielnia"
    circuits: List[Circuit] = field(default_factory=list)
    # 👉 NOWE: parametry widoku i lista modułów
    rows: int = 12
    cols: int = 18
    modules: List[Module] = field(default_factory=list)

@dataclass
class Cable:
    id: str
    a_element_id: str
    b_element_id: str
    kind: str = "YDYp 3x1.5"
    points: List[Tuple[int, int]] = field(default_factory=list)

@dataclass
class Project:
    id: str
    version: str = "1.2.0"
    name: str = "Domowy Elektryk — Projekt"
    boards: List[Board] = field(default_factory=list)
    elements: List[Element] = field(default_factory=list)
    cables: List[Cable] = field(default_factory=list)
    meta: Dict = field(default_factory=lambda: {"created": ts(), "updated": ts()})

    def to_dict(self) -> Dict:
        return asdict(self)

# ⏹ KONIEC KODU
