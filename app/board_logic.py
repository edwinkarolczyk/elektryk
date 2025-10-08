from typing import Optional, List
from .models import Project, Element, Board, Cable

ET_COLORS = {
    "GNIAZDKO": "#1f77b4",
    "LAMPA": "#ff7f0e",
    "ROLETY": "#2ca02c",
    "WLACZNIK": "#9467bd",
    "ROZDZIELNICA": "#111111",
}

ET_SHORT = {
    "GNIAZDKO": "G",
    "LAMPA": "L",
    "ROLETY": "R",
    "WLACZNIK": "W",
    "ROZDZIELNICA": "RG",
}

def next_symbol(project: Project, etype: str) -> str:
    prefix = ET_SHORT.get(etype, "X")
    used = []
    for e in project.elements:
        if e.etype == etype and "-" in e.name:
            try:
                used.append(int(e.name.split("-")[-1]))
            except: ...
    n = 1
    while n in used:
        n += 1
    if etype == "ROZDZIELNICA":
        return f"RG-{n}"
    return f"{prefix}-{n:02d}"

def find_board(project: Project, board_name: str) -> Optional[Board]:
    for b in project.boards:
        if b.name == board_name:
            return b
    return None

def validate_single_line(points: List[tuple]) -> List[tuple]:
    # Upraszczamy trasę do odcinków łamanych: max 12 punktów, traktowanych jako „jedna linia”
    if len(points) > 12:
        return points[:12]
    return points
