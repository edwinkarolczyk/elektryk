import json, os
from typing import Dict
from .models import Project, Board, Circuit, Element, Cable, Module, new_id

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PATH_PROJECT = os.path.join(DATA_DIR, "project.json")
os.makedirs(DATA_DIR, exist_ok=True)

def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path: str, payload: Dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_project() -> Project:
    raw = _read_json(PATH_PROJECT, {})
    if not raw:
        return seed_project()
    proj = Project(
        id=raw.get("id","proj-0001"),
        version=raw.get("version","1.2.0"),
        name=raw.get("name","Domowy Elektryk — Projekt"),
    )
    # Boards + circuits + modules
    for b in raw.get("boards", []):
        board = Board(
            id=b["id"], name=b["name"],
            location=b.get("location",""),
            rows=b.get("rows",12), cols=b.get("cols",18)
        )
        for c in b.get("circuits", []):
            board.circuits.append(Circuit(**c))
        for m in b.get("modules", []):
            board.modules.append(Module(**m))
        proj.boards.append(board)
    # Elements
    for e in raw.get("elements", []):
        proj.elements.append(Element(**e))
    # Cables
    for c in raw.get("cables", []):
        proj.cables.append(Cable(**c))
    proj.meta = raw.get("meta", proj.meta)
    return proj

def save_project(project: Project):
    project.meta["updated"] = project.meta.get("updated", 0) + 1
    _write_json(PATH_PROJECT, project.to_dict())

def seed_project() -> Project:
    # seed z przykładową rozdzielnicą i trzema obwodami + parę modułów
    b = Board(id=new_id("BRD"), name="RG-1", location="Korytarz", rows=8, cols=18)
    c1 = Circuit(id=new_id("CIR"), name="O1 Gniazda Salon", breaker="B16", rcd="30mA", color="#1256ff")
    c2 = Circuit(id=new_id("CIR"), name="O2 Oświetlenie Parter", breaker="B10", rcd=None, color="#ff7f0e")
    c3 = Circuit(id=new_id("CIR"), name="O3 Rolety", breaker="B16", rcd="30mA", color="#2ca02c")
    b.circuits += [c1, c2, c3]
    # przykładowe moduły (główny, RCD, MCB)
    b.modules += [
        Module(id=new_id("MOD"), kind="MAIN", label="FR", poles=2, row=0, col=0, color="#333333"),
        Module(id=new_id("MOD"), kind="RCD",  label="30mA", poles=2, row=0, col=2, color="#00897b"),
        Module(id=new_id("MOD"), kind="MCB",  label="B16 O1", poles=1, row=0, col=4, color="#1256ff", circuit_id=c1.id),
        Module(id=new_id("MOD"), kind="MCB",  label="B10 O2", poles=1, row=0, col=5, color="#ff7f0e", circuit_id=c2.id),
        Module(id=new_id("MOD"), kind="MCB",  label="B16 O3", poles=1, row=0, col=6, color="#2ca02c", circuit_id=c3.id),
        Module(id=new_id("MOD"), kind="SPD",  label="SPD",   poles=2, row=0, col=8, color="#6d4c41"),
    ]
    proj = Project(id=new_id("PRJ"))
    proj.boards.append(b)
    proj.elements += [
        Element(id=new_id("EL"), etype="ROZDZIELNICA", name="RG-1", x=80, y=300),
        Element(id=new_id("EL"), etype="GNIAZDKO", name="G-01", x=380, y=300, circuit_id=c1.id),
        Element(id=new_id("EL"), etype="LAMPA", name="L-01", x=620, y=160, circuit_id=c2.id),
        Element(id=new_id("EL"), etype="WLACZNIK", name="W-01", x=480, y=320, circuit_id=c2.id),
        Element(id=new_id("EL"), etype="ROLETY", name="R-01", x=750, y=320, circuit_id=c3.id),
    ]
    save_project(proj)
    return proj

# ⏹ KONIEC KODU
