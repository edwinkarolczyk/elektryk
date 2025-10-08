import json, os
from typing import Dict
from .models import Project, Board, Circuit, Element, Cable

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
    # prosty parser
    proj = Project(
        id=raw.get("id","proj-0001"),
        version=raw.get("version","1.0.0"),
        name=raw.get("name","Domowy Elektryk — Projekt"),
    )
    # boards
    for b in raw.get("boards", []):
        board = Board(id=b["id"], name=b["name"], location=b.get("location",""))
        for c in b.get("circuits", []):
            board.circuits.append(Circuit(**c))
        proj.boards.append(board)
    # elements
    for e in raw.get("elements", []):
        proj.elements.append(Element(**e))
    # cables
    for c in raw.get("cables", []):
        proj.cables.append(Cable(**c))
    proj.meta = raw.get("meta", proj.meta)
    return proj

def save_project(project: Project):
    project.meta["updated"] = project.meta.get("updated", 0) + 1
    _write_json(PATH_PROJECT, project.to_dict())

def seed_project() -> Project:
    from .models import new_id, Board, Circuit, Element, Project
    # domyślna rozdzielnica + 3 obwody
    b = Board(id=new_id("BRD"), name="RG-1", location="Korytarz")
    b.circuits.append(Circuit(id=new_id("CIR"), name="O1 Gniazda Salon", breaker="B16", rcd="30mA", color="#1256ff"))
    b.circuits.append(Circuit(id=new_id("CIR"), name="O2 Oświetlenie Parter", breaker="B10", rcd=None, color="#ff7f0e"))
    b.circuits.append(Circuit(id=new_id("CIR"), name="O3 Rolety", breaker="B16", rcd="30mA", color="#2ca02c"))
    proj = Project(id=new_id("PRJ"))
    proj.boards.append(b)
    # przykładowe elementy
    proj.elements += [
        Element(id=new_id("EL"), etype="ROZDZIELNICA", name="RG-1", x=80, y=300),
        Element(id=new_id("EL"), etype="GNIAZDKO", name="G-01", x=380, y=300, circuit_id=b.circuits[0].id),
        Element(id=new_id("EL"), etype="LAMPA", name="L-01", x=620, y=160, circuit_id=b.circuits[1].id),
        Element(id=new_id("EL"), etype="WLACZNIK", name="W-01", x=480, y=320, circuit_id=b.circuits[1].id),
        Element(id=new_id("EL"), etype="ROLETY", name="R-01", x=750, y=320, circuit_id=b.circuits[2].id),
    ]
    save_project(proj)
    return proj
