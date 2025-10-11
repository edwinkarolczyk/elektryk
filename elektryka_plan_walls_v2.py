# FILE: elektryka_plan_walls_v2.py
# Plan/Mapa: ŚCIANY + POKOJE • siatka w tle, przyciąganie, łączenie narożników,
# edycja, usuwanie, autosave JSON przy wyjściu. v2.0.0
# Autor: ChatGPT Codex — 2025-10-11

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
import json, os, tempfile, shutil

APP_TITLE = "Domowy Elektryk — Plan ścian (v2.0.0)"
GRID = 40                    # rozmiar kratki (px)
WALL_THICK = 6               # grubość ściany (px)
SNAP = GRID                  # przyciąganie do siatki
AUTOSAVE_FILE = "plan_walls.json"

# Kolory
COL_GRID = "#e5e7eb"
COL_BG   = "#fafafa"
COL_WALL = "#111111"
COL_SEL  = "#2563eb"
COL_ROOM = "#eef2ff"

ORIENTS = ("N", "S", "E", "W")

@dataclass
class Wall:
    id: str
    x: int     # lewy górny narożnik (po siatce)
    y: int
    w: int     # szerokość w px (dla N/S dł. w poziomie; dla E/W dł. w pionie)
    h: int
    orient: str  # N/S/E/W (informacyjne)
    north: Optional[str] = None
    south: Optional[str] = None
    east:  Optional[str] = None
    west:  Optional[str] = None

    def bbox(self) -> Tuple[int,int,int,int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)

    def set_neighbor(self, side: str, other_id: Optional[str]):
        if   side == "N": self.north = other_id
        elif side == "S": self.south = other_id
        elif side == "E": self.east  = other_id
        elif side == "W": self.west  = other_id

class PlanApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x800")
        self.minsize(900, 620)

        self.canvas = tk.Canvas(self, bg=COL_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._left_click)
        self.canvas.bind("<Button-3>", self._right_click)
        self.canvas.bind("<Motion>", self._motion)

        # Toolbar
        top = ttk.Frame(self)
        top.place(x=10, y=10)
        ttk.Button(top, text="➕ Ściana", command=self._add_wall_dialog).grid(row=0, column=0, padx=(0,6))
        ttk.Button(top, text="💾 Zapisz jako…", command=self._save_as).grid(row=0, column=1, padx=6)
        ttk.Button(top, text="📂 Otwórz…", command=self._open).grid(row=0, column=2, padx=6)
        ttk.Button(top, text="🧹 Wyczyść", command=self._clear).grid(row=0, column=3, padx=6)
        ttk.Label(top, text="(PPM na ścianie: Połącz/Edytuj/Usuń)").grid(row=0, column=4, padx=(10,0))

        self._hover_text_id: Optional[int] = None
        self._selected_wall_id: Optional[str] = None
        self._walls: Dict[str, Wall] = {}
        self._room_ids: List[int] = []  # rysowane pokoje
        self._dirty = False

        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="Połączenia…", command=lambda: self._connect_dialog(self._ctx_wall))
        self._menu.add_command(label="Edytuj element…", command=lambda: self._edit_wall_dialog(self._ctx_wall))
        self._menu.add_separator()
        self._menu.add_command(label="Usuń", command=lambda: self._delete_wall(self._ctx_wall))

        self._load_autosave()
        self._redraw_all()
        self.protocol("WM_DELETE_WINDOW", self._on_exit)

    # ==== RYSOWANIE ====
    def _draw_grid(self):
        self.canvas.delete("grid")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        for x in range(0, w, GRID):
            self.canvas.create_line(x, 0, x, h, fill=COL_GRID, tags="grid")
        for y in range(0, h, GRID):
            self.canvas.create_line(0, y, w, y, fill=COL_GRID, tags="grid")

    def _draw_walls(self):
        self.canvas.delete("wall")
        for wall in self._walls.values():
            x1,y1,x2,y2 = wall.bbox()
            color = COL_SEL if self._selected_wall_id == wall.id else COL_WALL
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color, tags=("wall", f"wall:{wall.id}"))
            # podpis orientacji na środku
            cx, cy = (x1+x2)//2, (y1+y2)//2
            self.canvas.create_text(cx, cy, text=wall.orient, fill="#ffffff", font=("Segoe UI", 9, "bold"), tags=("wall",))

    def _draw_rooms(self):
        # Prosta detekcja: jeśli mamy komplet N/S/E/W otaczających prostokąt o wspólnych krawędziach — zaznacz wnętrze.
        # Działa najlepiej przy łączeniu przez nasz dialog (bo dba o równe koordynaty).
        for rid in self._room_ids:
            self.canvas.delete(rid)
        self._room_ids.clear()

        # Szukamy „krzyża” sąsiedztw: wallN.south == wallS.id, wallW.east == wallE.id itd.
        walls = list(self._walls.values())
        for wn in [w for w in walls if w.orient == "N"]:
            # Dolna ściana musi mieć ten sam x i w
            ws = next((w for w in walls if w.orient == "S" and w.x == wn.x and w.w == wn.w), None)
            if not ws: continue
            # Lewa i prawa z dopasowaną wysokością
            ww = next((w for w in walls if w.orient == "W" and w.y == wn.y and w.h == ws.y - wn.y), None)
            we = next((w for w in walls if w.orient == "E" and w.y == wn.y and w.h == ws.y - wn.y and w.x == wn.x + wn.w - WALL_THICK), None)
            if not ww or not we: continue
            # Wnętrze
            inner_x1 = wn.x + WALL_THICK
            inner_y1 = wn.y + WALL_THICK
            inner_x2 = ws.x + ws.w - WALL_THICK
            inner_y2 = ws.y
            rid = self.canvas.create_rectangle(inner_x1, inner_y1, inner_x2, inner_y2, fill=COL_ROOM, outline="", stipple="gray50")
            self._room_ids.append(rid)

    def _redraw_all(self):
        self._draw_grid()
        self._draw_walls()
        self._draw_rooms()

    # ==== ZDARZENIA ====
    def _on_resize(self, _):
        self._draw_grid()

    def _left_click(self, event):
        wall_id = self._get_wall_at(event.x, event.y)
        self._selected_wall_id = wall_id
        self._redraw_all()

    def _right_click(self, event):
        wall_id = self._get_wall_at(event.x, event.y)
        if not wall_id:
            return
        self._ctx_wall = wall_id
        self._menu.tk_popup(event.x_root, event.y_root)

    def _motion(self, event):
        wall_id = self._get_wall_at(event.x, event.y)
        if wall_id:
            wall = self._walls[wall_id]
            text = f"{wall.id} • {wall.orient} • x:{wall.x} y:{wall.y} w:{wall.w} h:{wall.h}"
            self._show_hover(text, event.x, event.y)
        else:
            self._hide_hover()

    # ==== HOVER ====
    def _show_hover(self, text: str, x: int, y: int):
        self._hide_hover()
        self._hover_text_id = self.canvas.create_text(x+12, y+12, anchor="nw", text=text,
                                                      fill="#111827", font=("Segoe UI", 8), tags="hover")
        bbox = self.canvas.bbox(self._hover_text_id)
        if bbox:
            x1,y1,x2,y2 = bbox
            rect = self.canvas.create_rectangle(x1-6,y1-4,x2+6,y2+4, fill="#f1f5f9", outline="#94a3b8", tags="hover")
            self.canvas.tag_raise(self._hover_text_id, rect)

    def _hide_hover(self):
        if self._hover_text_id:
            self.canvas.delete("hover")
            self._hover_text_id = None

    # ==== KONTEKST: OPERACJE NA ŚCIANIE ====
    def _add_wall_dialog(self):
        orient = simpledialog.askstring("Nowa ściana", "Orientacja (N/S/E/W):", initialvalue="N")
        if not orient: return
        orient = orient.upper().strip()
        if orient not in ORIENTS:
            messagebox.showerror("Błąd", "Wpisz N / S / E / W"); return

        # pozycja i długość w kratkach
        gx = simpledialog.askinteger("Pozycja X (kratki)", "X (kratki):", initialvalue=5, minvalue=0)
        gy = simpledialog.askinteger("Pozycja Y (kratki)", "Y (kratki):", initialvalue=5, minvalue=0)
        glen = simpledialog.askinteger("Długość (kratki)", "Długość (kratki):", initialvalue=8, minvalue=1)
        if gx is None or gy is None or glen is None: return

        x = gx * GRID; y = gy * GRID
        if orient in ("N","S"):
            w, h = glen * GRID, WALL_THICK
        else:
            w, h = WALL_THICK, glen * GRID

        wall_id = self._new_wall_id()
        self._walls[wall_id] = Wall(wall_id, x, y, w, h, orient)
        self._selected_wall_id = wall_id
        self._mark_dirty()
        self._redraw_all()

    def _edit_wall_dialog(self, wall_id: str):
        w = self._walls[wall_id]
        orient = simpledialog.askstring("Edycja ściany", "Orientacja (N/S/E/W):", initialvalue=w.orient)
        if not orient: return
        orient = orient.upper().strip()
        if orient not in ORIENTS:
            messagebox.showerror("Błąd", "Wpisz N / S / E / W"); return

        gx = simpledialog.askinteger("Pozycja X (kratki)", "X (kratki):", initialvalue=w.x//GRID, minvalue=0)
        gy = simpledialog.askinteger("Pozycja Y (kratki)", "Y (kratki):", initialvalue=w.y//GRID, minvalue=0)
        glen = simpledialog.askinteger("Długość (kratki)", "Długość (kratki):",
                                       initialvalue=(w.w//GRID if w.orient in ("N","S") else w.h//GRID), minvalue=1)
        if gx is None or gy is None or glen is None: return

        x = gx * GRID; y = gy * GRID
        if orient in ("N","S"):
            width, height = glen * GRID, WALL_THICK
        else:
            width, height = WALL_THICK, glen * GRID

        w.x, w.y, w.w, w.h, w.orient = x, y, width, height, orient
        self._mark_dirty()
        self._redraw_all()

    def _delete_wall(self, wall_id: str):
        if not messagebox.askyesno("Usuń", f"Usunąć ścianę {wall_id}?"):
            return
        # odetnij sąsiadów wskazujących na ten element
        for ww in self._walls.values():
            for side in ("N","S","E","W"):
                if self._get_neighbor_id(ww, side) == wall_id:
                    ww.set_neighbor(side, None)
        self._walls.pop(wall_id, None)
        if self._selected_wall_id == wall_id:
            self._selected_wall_id = None
        self._mark_dirty()
        self._redraw_all()

    def _connect_dialog(self, wall_id: str):
        if not wall_id: return
        # wybierz stronę łączenia i drugą ścianę
        side = simpledialog.askstring("Połącz", "Którą stroną łączyć? (N/S/E/W):", initialvalue="N")
        if not side: return
        side = side.upper().strip()
        if side not in ORIENTS:
            messagebox.showerror("Błąd", "Wpisz N / S / E / W"); return

        others = [wid for wid in self._walls.keys() if wid != wall_id]
        if not others:
            messagebox.showinfo("Połącz", "Brak innej ściany do połączenia.")
            return
        choice = simpledialog.askstring("Połącz z…", f"Wpisz ID ściany z listy:\n{', '.join(others)}", initialvalue=others[0])
        if not choice or choice not in self._walls:
            return

        ok = self._connect_walls(wall_id, side, choice)
        if ok:
            self._mark_dirty()
            self._redraw_all()
        else:
            messagebox.showwarning("Połącz", "Nie udało się dopasować ścian (sprawdź orientacje/długości).")

    # właściwe łączenie: przeskalowanie/ustawienie pozycji 2. ściany do styku krawędzi
    def _connect_walls(self, a_id: str, side: str, b_id: str) -> bool:
        A = self._walls[a_id]
        B = self._walls[b_id]

        # Normalizuj: jeżeli łączymy N/S, to B musi być pozioma; E/W – B pionowa.
        if side in ("N","S") and B.orient not in ("N","S"): return False
        if side in ("E","W") and B.orient not in ("E","W"): return False

        if side == "N":
            # B (pozioma) ustaw nad A: x dopasuj do A.x, długość równa A.w
            B.x = A.x
            B.w = A.w
            B.y = A.y - WALL_THICK
            A.set_neighbor("N", b_id); B.set_neighbor("S", a_id)
        elif side == "S":
            B.x = A.x
            B.w = A.w
            B.y = A.y + A.h
            A.set_neighbor("S", b_id); B.set_neighbor("N", a_id)
        elif side == "W":
            # B (pionowa) ustaw po lewej: y dopasuj, wysokość równa A.h
            B.y = A.y
            B.h = A.h
            B.x = A.x - WALL_THICK
            A.set_neighbor("W", b_id); B.set_neighbor("E", a_id)
        elif side == "E":
            B.y = A.y
            B.h = A.h
            B.x = A.x + A.w
            A.set_neighbor("E", b_id); B.set_neighbor("W", a_id)
        return True

    # ==== POMOCNICZE ====
    def _get_wall_at(self, x: int, y: int) -> Optional[str]:
        # hit test
        for wid, w in self._walls.items():
            x1,y1,x2,y2 = w.bbox()
            if x1 <= x <= x2 and y1 <= y <= y2:
                return wid
        return None

    def _get_neighbor_id(self, w: Wall, side: str) -> Optional[str]:
        return {"N": w.north, "S": w.south, "E": w.east, "W": w.west}[side]

    def _new_wall_id(self) -> str:
        i = 1
        while True:
            wid = f"W{i:03d}"
            if wid not in self._walls:
                return wid
            i += 1

    def _mark_dirty(self):
        self._dirty = True

    # ==== PLIK / JSON ====
    def _state(self) -> dict:
        return {
            "version": "2.0.0",
            "grid": GRID,
            "walls": [asdict(w) for w in self._walls.values()]
        }

    def _apply_state(self, data: dict):
        self._walls.clear()
        for w in data.get("walls", []):
            self._walls[w["id"]] = Wall(**w)

    def _save_to(self, path: str):
        data = self._state()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="plan.", suffix=".json", dir=os.path.dirname(path) or ".")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, path)  # atomic replace
        self._dirty = False

    def _load_from(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_state(data)
            self._dirty = False
            return True
        except Exception as e:
            messagebox.showerror("Otwórz", f"Nie udało się wczytać pliku:\n{e}")
            return False

    def _save_as(self):
        path = filedialog.asksaveasfilename(title="Zapisz plan ścian", defaultextension=".json",
                                            filetypes=[("JSON","*.json")], initialfile=AUTOSAVE_FILE)
        if not path: return
        self._save_to(path)

    def _open(self):
        path = filedialog.askopenfilename(title="Otwórz plan ścian", filetypes=[("JSON","*.json")])
        if not path: return
        if self._load_from(path):
            self._redraw_all()

    def _clear(self):
        if self._walls and not messagebox.askyesno("Wyczyść", "Usunąć wszystkie ściany?"):
            return
        self._walls.clear()
        self._selected_wall_id = None
        self._dirty = True
        self._redraw_all()

    def _load_autosave(self):
        self._load_from(AUTOSAVE_FILE)

    def _on_exit(self):
        # autosave do pliku w katalogu roboczym
        if self._dirty or not os.path.exists(AUTOSAVE_FILE):
            try:
                self._save_to(AUTOSAVE_FILE)
            except Exception:
                pass
        self.destroy()

if __name__ == "__main__":
    PlanApp().mainloop()
# ⏹ KONIEC KODU
