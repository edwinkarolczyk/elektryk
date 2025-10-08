from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
import uuid
import time

ElementType = str  # "GNIAZDKO","LAMPA","ROLETY","WLACZNIK","ROZDZIELNICA"

def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

def ts() -> int:
    return int(time.time())

@dataclass
class Element:
    id: str
    etype: ElementType
    name: str       # np. G-01 / L-01 ...
    x: int = 50
    y: int = 50
    room: Optional[str] = None
    notes: str = ""
    circuit_id: Optional[str] = None   # przypięty obwód (z rozdzielnicy)

@dataclass
class Circuit:
    id: str
    name: str       # np. B16/O1 „Gniazda salon”
    breaker: str    # np. B16, B10, C20
    rcd: Optional[str] = None  # np. 30mA
    color: str = "#000000"
    enabled: bool = True
    load_va: int = 0

@dataclass
class Board:
    id: str
    name: str
    location: str = "Rozdzielnia"
    circuits: List[Circuit] = field(default_factory=list)

@dataclass
class Cable:
    id: str
    a_element_id: str
    b_element_id: str
    kind: str = "YDYp 3x1.5"
    points: List[Tuple[int, int]] = field(default_factory=list)  # jedna linia (polyline), ale traktowana jako „jedna trasa”

@dataclass
class Project:
    id: str
    version: str = "1.0.0"
    name: str = "Domowy Elektryk — Projekt"
    boards: List[Board] = field(default_factory=list)
    elements: List[Element] = field(default_factory=list)
    cables: List[Cable] = field(default_factory=list)
    meta: Dict = field(default_factory=lambda: {"created": ts(), "updated": ts()})

    def to_dict(self) -> Dict:
        return asdict(self)
