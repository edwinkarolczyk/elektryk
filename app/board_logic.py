from typing import Optional
from .models import Project, Element, Board, Circuit

ET_COLORS = {
    "GNIAZDKO": "#1f77b4",
    "LAMPA": "#ff7f0e",
    "ROLETY": "#2ca02c",
    "WLACZNIK": "#9467bd",
    "ROZDZIELNICA": "#111111",
}

ET_SHORT = {"GNIAZDKO":"G","LAMPA":"L","ROLETY":"R","WLACZNIK":"W","ROZDZIELNICA":"RG"}

def next_symbol(project: Project, etype: str) -> str:
    prefix = ET_SHORT.get(etype, "X")
    used = []
    for e in project.elements:
        if e.etype == etype and "-" in e.name:
            try:
                used.append(int(e.name.split("-")[-1]))
            except Exception:
                pass
    n = 1
    while n in used:
        n += 1
    return f"RG-{n}" if etype == "ROZDZIELNICA" else f"{prefix}-{n:02d}"

def circuit_of_element(project: Project, el: Element) -> Optional[Circuit]:
    if not el.circuit_id:
        return None
    for b in project.boards:
        for c in b.circuits:
            if c.id == el.circuit_id:
                return c
    return None

def find_board(project: Project, name: str) -> Optional[Board]:
    for b in project.boards:
        if b.name == name:
            return b
    return None

def clamp(v, a, b):
    return max(a, min(b, v))

# ⏹ KONIEC KODU
