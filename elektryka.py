# Elektryka 0.7.0
# Nowe:
# - Rysowanie połączeń między elementami (Linki) w kolorze wybranego obwodu
# - Tryb "Origami" układu pokoju: rysowanie segmentów: ŚCIANA / OKNO / DRZWI / PRZEJŚCIE
# - Panel: przełącznik Pokaż połączenia
# - Segmenty pojawiają się w PDF (kolorami), wraz z legendą obwodów
#
# Uwaga: minimalna ingerencja w istniejący kod (0.6.0) — dodane dataclassy, kilka paneli i rysowanie.

import json, os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
    Image = ImageDraw = ImageTk = None

APP_TITLE = "Elektryka 0.7.0"
SETTINGS_FILE = "settings.json"
PROJECT_FILE_DEFAULT = "project.json"

# ================== DANE ==================
@dataclass
class Connection:
    cable_type: str
    conductors: Dict[str, bool]
    to_distribution: bool = True
    note: str = ""
    circuit_id: Optional[str] = None

@dataclass
class Element:
    id: str
    type: str
    x: int
    y: int
    label: str = ""
    variant: str = ""
    power_w: Optional[float] = None
    chain_prev: Optional[str] = None
    controls: List[str] = field(default_factory=list)
    connections: List[Connection] = field(default_factory=list)
    max_current_a: Optional[float] = None

# --- NOWE: układ pokoju (origami) ---
@dataclass
class Segment:
    kind: str              # "SCIANA" | "OKNO" | "DRZWI" | "PRZEJSCIE"
    a: Tuple[int,int]      # (x1,y1)
    b: Tuple[int,int]      # (x2,y2)

@dataclass
class Link:
    a_id: str              # element id źródło
    b_id: str              # element id cel
    circuit_id: Optional[str] = None
    note: str = ""

@dataclass
class Room:
    name: str
    background_image: str = ""
    elements: List[Element] = field(default_factory=list)
    # NOWE:
    segments: List[Segment] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)

@dataclass
class House:
    name: str
    rooms: List[Room] = field(default_factory=list)

@dataclass
class Circuit:
    id: str
    name: str
    color: str = "czarny"
    breaker: str = ""
    desc: str = ""
    assigned_leads: List[str] = field(default_factory=list)

@dataclass
class Project:
    version: str = "0.7.0"
    houses: List[House] = field(default_factory=list)
    circuits: List[Circuit] = field(default_factory=list)
    distribution_board: dict = field(default_factory=lambda: {"free_leads": []})
    meta: dict = field(default_factory=dict)

# ================== APP ==================
class ElektrykaApp:
    def __init__(self, root: tk.Tk):
        self.root = root; root.title(APP_TITLE)
        self.settings = self._load_settings()
        self.project = Project()

        self.current_house_idx = 0
        self.current_room_idx = 0

        self.bg_image = None; self.bg_pil = None

        # widok / filtry
        self.only_circuit_var = tk.BooleanVar(value=False)
        self.filter_circuit_var = tk.StringVar(value="")
        self.show_chips_var = tk.BooleanVar(value=self.settings["ui"].get("show_conductor_chips_on_canvas", True))
        self.show_links_var = tk.BooleanVar(value=True)  # NOWE: pokaż połączenia

        # tryb rysowania układu (origami)
        self.layout_draw_mode = tk.BooleanVar(value=False)
        self.segment_kind_var = tk.StringVar(value="SCIANA")
        self._layout_prev_point: Optional[Tuple[int,int]] = None

        self._build_ui()
        self._bind_keys()
        self._ensure_defaults()
        self._refresh_lists()
        self._redraw()

    # ---------- settings ----------
    def _load_settings(self):
        try:
            with open(SETTINGS_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            messagebox.showwarning("Settings","Brak settings.json — używam domyślnych.")
            return {
                "ui":{"show_grid":True,"snap_to_grid":True,"default_grid_size":20,"show_conductor_chips_on_canvas":True,"auto_open_connections_dialog_on_place":True},
                "limits":{"max_connections_per_element":4,"voltage_drop_lighting":3.0,"voltage_drop_general":5.0,"load_warning":0.8,"load_error":1.0,"socket_default_current_a":16.0},
                "element_types":{"gniazdko":{},"wylacznik_1":{},"wylacznik_2":{},"roleta":{},"lampa":{}},
                "colors":{"conductors":{"L":"#a52a2a","N":"#1a73e8","PE":"#9acd32","L1":"#a52a2a","L2":"#000000","L3":"#808080"},
                          "circuit_palette":{"niebieski":"#1a73e8","czarny":"#000000","zolto-zielony":"#9acd32","szary":"#808080"}}
            }

    # ---------- helpers ----------
    def _cur_house(self) -> House:
        if not self.project.houses:
            self.project.houses.append(House(name="Dom 1", rooms=[Room(name="Sypialnia")]))
        self.current_house_idx = max(0, min(self.current_house_idx, len(self.project.houses)-1))
        return self.project.houses[self.current_house_idx]

    def _cur_room(self) -> Room:
        h = self._cur_house()
        if not h.rooms: h.rooms.append(Room(name="Sypialnia"))
        self.current_room_idx = max(0, min(self.current_room_idx, len(h.rooms)-1))
        return h.rooms[self.current_room_idx]

    def _ensure_defaults(self):
        if not self.project.houses:
            self.project.houses = [House(name="Dom 1", rooms=[Room(name="Sypialnia")])]
        if not self.project.circuits:
            self.project.circuits = [
                Circuit(id="O1", name="Gniazda sypialnia", color="niebieski", breaker="B16"),
                Circuit(id="O2", name="Światło sypialnia", color="czarny", breaker="B10"),
                Circuit(id="O99", name="Płyta indukcyjna", color="szary", breaker="C16")
            ]

    # ---------- UI ----------
    def _build_ui(self):
        self.root.geometry("1600x950"); self.root.minsize(1200,780)
        self.main = ttk.Frame(self.root); self.main.pack(fill="both", expand=True)

        # LEFT
        left = ttk.Frame(self.main, width=280); left.pack(side="left", fill="y")

        ttk.Label(left, text="Domy", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8,2))
        self.lb_houses = tk.Listbox(left, height=4, exportselection=False); self.lb_houses.pack(fill="x", padx=8)
        self.lb_houses.bind("<<ListboxSelect>>", lambda e:self._on_house_select())
        hb = ttk.Frame(left); hb.pack(fill="x", padx=8, pady=4)
        ttk.Button(hb, text="+ Dom", command=self._add_house).pack(side="left")
        ttk.Button(hb, text="Usuń", command=self._del_house).pack(side="left", padx=6)

        ttk.Separator(left).pack(fill="x", padx=8, pady=8)
        ttk.Label(left, text="Pomieszczenia", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8)
        self.lb_rooms = tk.Listbox(left, height=6, exportselection=False); self.lb_rooms.pack(fill="x", padx=8)
        self.lb_rooms.bind("<<ListboxSelect>>", lambda e:self._on_room_select())
        rb = ttk.Frame(left); rb.pack(fill="x", padx=8, pady=4)
        ttk.Button(rb, text="+ Pokój", command=self._add_room).pack(side="left")
        ttk.Button(rb, text="Usuń", command=self._del_room).pack(side="left", padx=6)

        ttk.Separator(left).pack(fill="x", padx=8, pady=8)
        ttk.Label(left, text="Tło pokoju (JPG/JPEG/PNG)", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        ttk.Button(left, text="Wczytaj tło pokoju…", command=self.load_background).pack(fill="x", padx=8, pady=(2,0))
        ttk.Button(left, text="Wyczyść tło pokoju", command=self.clear_background).pack(fill="x", padx=8, pady=4)

        ttk.Separator(left).pack(fill="x", padx=8, pady=8)
        ttk.Label(left, text="Elementy (narzędzie)", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8)
        self.tool_list = list(self.settings.get("element_types", {}).keys()) or ["gniazdko","wylacznik_1","wylacznik_2","roleta","lampa"]
        self.tool_var = tk.StringVar(value=self.tool_list[0])
        for t in self.tool_list:
            ttk.Radiobutton(left, text=t, value=t, variable=self.tool_var).pack(anchor="w", padx=12)

        # --- NOWE: tryb układu (origami) ---
        ttk.Separator(left).pack(fill="x", padx=8, pady=8)
        ttk.Label(left, text="Układ pokoju (origami)", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8)
        ttk.Checkbutton(left, text="Tryb rysowania układu", variable=self.layout_draw_mode).pack(anchor="w", padx=12)
        kind_row = ttk.Frame(left); kind_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(kind_row, text="Typ segmentu:").pack(side="left")
        ttk.Combobox(kind_row, textvariable=self.segment_kind_var,
                     values=["SCIANA","OKNO","DRZWI","PRZEJSCIE"], state="readonly", width=12).pack(side="left", padx=6)
        lr = ttk.Frame(left); lr.pack(fill="x", padx=8, pady=4)
        ttk.Button(lr, text="Zakończ odcinek (PPM też)", command=self._finish_segment_poly).pack(side="left")
        ttk.Button(lr, text="Wyczyść układ", command=self._clear_layout).pack(side="left", padx=6)

        # RIGHT
        right = ttk.Frame(self.main, width=380); right.pack(side="right", fill="y")
        ttk.Label(right, text="Obwody", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8,2))
        self.tv_circuits = ttk.Treeview(right, columns=("name","color","breaker"), show="headings", height=8)
        self.tv_circuits = ttk.Treeview(
    right, columns=("name", "color", "breaker"), show="headings", height=8
)
self.tv_circuits.heading("name", text="Nazwa")
self.tv_circuits.heading("color", text="Kolor")
self.tv_circuits.heading("breaker", text="Zabezp.")
self.tv_circuits.column("name", width=180)
self.tv_circuits.column("color", width=90)
self.tv_circuits.column("breaker", width=90)
self.tv_circuits.pack(fill="x", padx=8)

        self.tv_circuits.column("name",width=180); self.tv_circuits.column("color",width=90); self.tv_circuits.column("breaker",width=90)
        self.tv_circuits.pack(fill="x", padx=8)
        cb = ttk.Frame(right); cb.pack(fill="x", padx=8, pady=4)
        ttk.Button(cb, text="+ Dodaj obwód", command=self._add_circuit).pack(side="left")
        ttk.Button(cb, text="Edytuj", command=self._edit_circuit).pack(side="left", padx=6)
        ttk.Button(cb, text="Usuń", command=self._del_circuit).pack(side="left")

        ttk.Separator(right).pack(fill="x", padx=8, pady=8)
        ttk.Label(right, text="Widok", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        ttk.Checkbutton(right, text="Pokaż tylko wybrany obwód", variable=self.only_circuit_var, command=self._redraw).pack(anchor="w", padx=12)
        self.filter_combo = ttk.Combobox(right, values=[], textvariable=self.filter_circuit_var, state="readonly")
        self.filter_combo.pack(fill="x", padx=8, pady=(2,6))
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._redraw())
        def _toggle_chips():
            self.settings["ui"]["show_conductor_chips_on_canvas"] = self.show_chips_var.get(); self._redraw()
        ttk.Checkbutton(right, text="Paski żył przy elementach", variable=self.show_chips_var, command=_toggle_chips).pack(anchor="w", padx=12)
        ttk.Checkbutton(right, text="Pokaż połączenia", variable=self.show_links_var, command=self._redraw).pack(anchor="w", padx=12)

        ttk.Separator(right).pack(fill="x", padx=8, pady=8)
        ttk.Label(right, text="Wolne przewody", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        self.tv_leads = ttk.Treeview(right, columns=("lead","room","elem","cable"), show="headings", height=9)
        for h in ("lead","room","elem","cable"):
            self.tv_leads.heading(h, text=h.upper())
        self.tv_leads.column("lead", width=90); self.tv_leads.column("room", width=110)
        self.tv_leads.column("elem", width=80); self.tv_leads.column("cable", width=80)
        self.tv_leads.pack(fill="x", padx=8)
        lb = ttk.Frame(right); lb.pack(fill="x", padx=8, pady=4)
        ttk.Button(lb, text="Przypisz do zazn. obwodu", command=self._assign_leads_to_selected_circuit).pack(side="left")

        ttk.Separator(right).pack(fill="x", padx=8, pady=8)
        ttk.Button(right, text="Eksport PDF pokoju", command=self.export_pdf).pack(fill="x", padx=8, pady=(0,8))

        # CENTER
        self.canvas = tk.Canvas(self.main, bg="white")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_left)
        self.canvas.bind("<Button-3>", self._on_canvas_right)
        self.canvas.bind("<Configure>", lambda e:self._redraw())

        # status
        self.status = tk.StringVar(value="Gotowy")
        ttk.Label(self.root, textvariable=self.status, anchor="w").pack(side="bottom", fill="x")

        # menu
        menubar = tk.Menu(self.root)
        mfile = tk.Menu(menubar, tearoff=False)
        mfile.add_command(label="Wczytaj projekt (JSON)", command=self.load_project)
        mfile.add_command(label="Zapisz projekt (JSON)", command=self.save_project)
        mfile.add_separator()
        mfile.add_command(label="Eksport PDF pokoju", command=self.export_pdf)
        mfile.add_separator()
        mfile.add_command(label="Wyjście", command=self.root.destroy)
        menubar.add_cascade(label="Plik", menu=mfile)
        self.root.config(menu=menubar)

    def _bind_keys(self):
        self.root.bind("<Control-s>", lambda e:self.save_project())
        self.root.bind("<Control-o>", lambda e:self.load_project())

    # ---------- refresh lists ----------
    def _refresh_lists(self):
        self.lb_houses.delete(0,"end")
        for h in self.project.houses: self.lb_houses.insert("end", h.name)
        if self.project.houses: self.lb_houses.selection_set(self.current_house_idx)

        self.lb_rooms.delete(0,"end")
        for r in self._cur_house().rooms: self.lb_rooms.insert("end", r.name)
        if self._cur_house().rooms: self.lb_rooms.selection_set(self.current_room_idx)

        for i in self.tv_circuits.get_children(): self.tv_circuits.delete(i)
        for c in self.project.circuits:
            self.tv_circuits.insert("", "end", iid=c.id, values=(c.name, c.color, c.breaker))

        self.filter_combo["values"] = [""] + [c.id for c in self.project.circuits]
        if self.filter_circuit_var.get() not in self.filter_combo["values"]:
            self.filter_circuit_var.set("")

        for i in self.tv_leads.get_children(): self.tv_leads.delete(i)
        for lead in self.project.distribution_board.get("free_leads", []):
            self.tv_leads.insert("", "end", iid=lead["lead_id"],
                                 values=(lead["lead_id"], lead["room"], lead["element_id"], lead["cable_type"]))

        self._load_room_background()

    # ---------- dom/pokój ----------
    def _on_house_select(self):
        s = self.lb_houses.curselection()
        if s: self.current_house_idx = s[0]; self.current_room_idx = 0; self._refresh_lists(); self._redraw()

    def _on_room_select(self):
        s = self.lb_rooms.curselection()
        if s: self.current_room_idx = s[0]; self._load_room_background(); self._redraw()

    def _add_house(self):
        self.project.houses.append(House(name=f"Dom {len(self.project.houses)+1}", rooms=[Room(name="Pokój 1")]))
        self.current_house_idx = len(self.project.houses)-1; self.current_room_idx = 0
        self._refresh_lists()

    def _del_house(self):
        if not self.project.houses: return
        del self.project.houses[self.current_house_idx]
        self.current_house_idx = 0; self.current_room_idx = 0
        self._refresh_lists(); self._redraw()

    def _add_room(self):
        h = self._cur_house(); h.rooms.append(Room(name=f"Pokój {len(h.rooms)+1}"))
        self.current_room_idx = len(h.rooms)-1
        self._refresh_lists()

    def _del_room(self):
        h = self._cur_house()
        if not h.rooms: return
        del h.rooms[self.current_room_idx]
        self.current_room_idx = 0
        self._refresh_lists(); self._redraw()

    # ---------- tło ----------
    def load_background(self):
        path = filedialog.askopenfilename(title="Wybierz tło",
            filetypes=[("Obrazy","*.jpg;*.jpeg;*.png;*.JPG;*.JPEG;*.PNG")])
        if not path: return
        r = self._cur_room(); r.background_image = os.path.abspath(path)
        self._load_room_background(); self._redraw()

    def clear_background(self):
        r = self._cur_room(); r.background_image = ""
        self.bg_image = None; self.bg_pil = None; self._redraw()

    def _load_room_background(self):
        r = self._cur_room()
        self.bg_image = None; self.bg_pil = None
        if r.background_image and os.path.exists(r.background_image) and PIL_AVAILABLE:
            try:
                self.bg_pil = Image.open(r.background_image).convert("RGB")
                self.bg_image = ImageTk.PhotoImage(self.bg_pil)
            except Exception as e:
                messagebox.showwarning("Tło", f"Problem z wczytaniem tła:\n{e}")

    # ---------- CANVAS interaction ----------
    def _grid_snap(self, x, y):
        if self.settings["ui"].get("snap_to_grid", True):
            gs = self.settings["ui"].get("default_grid_size", 20)
            x = round(x/gs)*gs; y = round(y/gs)*gs
        return x,y

    def _on_canvas_left(self, event):
        if self.layout_draw_mode.get():
            # tryb rysowania układu: klik = kolejny punkt segmentu
            x,y = self._grid_snap(event.x, event.y)
            if self._layout_prev_point is None:
                self._layout_prev_point = (x,y)
            else:
                a = self._layout_prev_point; b = (x,y)
                self._cur_room().segments.append(Segment(kind=self.segment_kind_var.get(), a=a, b=b))
                self._layout_prev_point = b
            self._redraw(); return

        # dodawanie elementów
        x,y = self._grid_snap(event.x, event.y)
        r = self._cur_room()
        eid = f"E-{len(r.elements)+1:03d}"
        el = Element(id=eid, type=self.tool_var.get(), x=x, y=y)
        if el.type.startswith("gniazdko"):
            el.max_current_a = float(self.settings["limits"].get("socket_default_current_a", 16.0))
        r.elements.append(el)
        self._redraw()
        if self.settings["ui"].get("auto_open_connections_dialog_on_place", True):
            self._open_connections_dialog(el)

    def _on_canvas_right(self, event):
        if self.layout_draw_mode.get():
            self._finish_segment_poly()
            return

        # menu elementu
        nearest = self.canvas.find_closest(event.x, event.y)
        if not nearest: return
        cid = nearest[0]
        for t in self.canvas.gettags(cid):
            if t.startswith("el:"):
                eid = t.split(":")[1]
                el = next((e for e in self._cur_room().elements if e.id == eid), None)
                if not el: return
                menu = tk.Menu(self.root, tearoff=False)
                menu.add_command(label="Połączenia…", command=lambda:self._open_connections_dialog(el))
                menu.add_command(label="Edytuj element…", command=lambda:self._open_element_editor(el))
                menu.add_command(label="Połącz z…", command=lambda:self._open_link_dialog(el))  # NOWE
                menu.post(event.x_root, event.y_root)
                return

    def _finish_segment_poly(self):
        self._layout_prev_point = None
        self.status.set("Zakończono ciąg segmentów.")

    def _clear_layout(self):
        r = self._cur_room(); r.segments.clear(); self._layout_prev_point=None; self._redraw()

    # ---------- rysowanie ----------
    def _draw_grid(self):
        if not self.settings["ui"].get("show_grid", True): return
        gs = self.settings["ui"].get("default_grid_size", 20)
        w=self.canvas.winfo_width(); h=self.canvas.winfo_height()
        for x in range(0, w, gs): self.canvas.create_line(x,0,x,h, fill="#eeeeee")
        for y in range(0, h, gs): self.canvas.create_line(0,y,w,y, fill="#eeeeee")

    def _draw_background(self):
        if self.bg_image is not None:
            self.canvas.create_image(0,0, image=self.bg_image, anchor="nw")

    def _circuit_color_hex(self, circ_id: Optional[str]) -> str:
        if not circ_id: return "#555555"
        c = next((c for c in self.project.circuits if c.id == circ_id), None)
        if not c: return "#555555"
        return self.settings["colors"]["circuit_palette"].get(c.color, "#000000")

    def _color_hex(self, key):
        return self.settings["colors"]["conductors"].get(key, "#000000")

    def _draw_segments(self):
        # kolory segmentów
        palette = {
            "SCIANA": "#2b2b2b",
            "OKNO": "#1a73e8",
            "DRZWI": "#a52a2a",
            "PRZEJSCIE": "#9acd32",
        }
        for s in self._cur_room().segments:
            col = palette.get(s.kind, "#2b2b2b")
            width = 4 if s.kind=="SCIANA" else 3
            dash = () if s.kind in ("SCIANA","DRZWI") else (6,4)
            self.canvas.create_line(s.a[0], s.a[1], s.b[0], s.b[1], fill=col, width=width, dash=dash)

    def _draw_element(self, el: Element):
        r=8
        self.canvas.create_oval(el.x-r, el.y-r, el.x+r, el.y+r, outline="#000", fill="#fff", tags=("el",f"el:{el.id}"))
        if el.label: self.canvas.create_text(el.x, el.y-12, text=el.label, fill="#333")

        if self.settings["ui"].get("show_conductor_chips_on_canvas", True) and el.connections:
            con = el.connections[0]
            x_off = el.x + 12; y_off = el.y - 8
            for k,used in con.conductors.items():
                if used:
                    c = self._color_hex(k)
                    self.canvas.create_rectangle(x_off, y_off, x_off+20, y_off+12, outline="#222", fill=c, tags=("el",f"el:{el.id}"))
                    self.canvas.create_text(x_off+10, y_off+6, text=k, fill="#fff", font=("Segoe UI", 7, "bold"), tags=("el",f"el:{el.id}"))
                    x_off += 24

        if el.max_current_a:
            try:
                w = el.max_current_a * 230.0
                self.canvas.create_text(el.x, el.y + 16, text=f"{el.max_current_a:.0f}A", fill="#444", font=("Segoe UI", 8))
                self.canvas.create_text(el.x, el.y + 28, text=f"~{int(w)}W", fill="#888", font=("Segoe UI", 7))
            except:
                pass

    def _draw_links(self):
        if not self.show_links_var.get(): return
        only = self.only_circuit_var.get()
        pick = self.filter_circuit_var.get().strip()
        room = self._cur_room()
        # mapa id->element
        idx = {e.id: e for e in room.elements}
        for link in room.links:
            if link.a_id not in idx or link.b_id not in idx: continue
            if only and pick and (link.circuit_id != pick): continue
            a = idx[link.a_id]; b = idx[link.b_id]
            color = self._circuit_color_hex(link.circuit_id)
            self.canvas.create_line(a.x, a.y, b.x, b.y, fill=color, width=3, arrow="last")

    def _redraw(self):
        self.canvas.delete("all")
        self._draw_background()
        self._draw_grid()
        self._draw_segments()

        only = self.only_circuit_var.get()
        pick = self.filter_circuit_var.get().strip()
        for el in self._cur_room().elements:
            if only and pick:
                in_circ = any(getattr(con, "circuit_id", None) == pick for con in el.connections)
                if not in_circ: 
                    continue
            self._draw_element(el)

        self._draw_links()

    # ---------- edycje ----------
    def _open_element_editor(self, el: Element):
        d = tk.Toplevel(self.root); d.title(f"Element: {el.id}"); d.transient(self.root); d.grab_set()

        fr1 = ttk.Frame(d); fr1.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr1, text="Etykieta:", width=14).pack(side="left")
        e_label = ttk.Entry(fr1); e_label.pack(side="left", fill="x", expand=True); e_label.insert(0, el.label or "")

        fr2 = ttk.Frame(d); fr2.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr2, text="Max prąd [A]:", width=14).pack(side="left")
        e_ma = ttk.Entry(fr2, width=10); e_ma.pack(side="left")
        e_ma.insert(0, str(el.max_current_a if el.max_current_a is not None else
                           self.settings["limits"].get("socket_default_current_a", 16.0) if el.type.startswith("gniazdko") else ""))

        fr4 = ttk.Frame(d); fr4.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr4, text="Moc [W]:", width=14).pack(side="left")
        e_pw = ttk.Entry(fr4, width=12); e_pw.pack(side="left")
        e_pw.insert(0, "" if el.power_w is None else str(el.power_w))

        same_type_ids = [e.id for e in self._cur_room().elements if e.id != el.id and e.type == el.type]
        fr3 = ttk.Frame(d); fr3.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr3, text="Ciąg dalszy z:", width=14).pack(side="left")
        chain_var = tk.StringVar(value=el.chain_prev or "")
        ttk.Combobox(fr3, textvariable=chain_var, values=[""]+same_type_ids, width=14, state="readonly").pack(side="left")

        info = ttk.Label(d, foreground="#555"); info.pack(anchor="w", padx=8, pady=(0,8))
        try:
            ma = float(e_ma.get())
            if ma > 0:
                info.config(text=f"Sugerowane max: {ma:.0f} A @ 230 V ≈ {ma*230:.0f} W")
        except: pass

        def ok():
            el.label = e_label.get().strip()
            try:
                v = e_ma.get().strip(); el.max_current_a = float(v) if v else None
            except: el.max_current_a = None
            try:
                v = e_pw.get().strip(); el.power_w = float(v) if v else None
            except: el.power_w = None
            el.chain_prev = chain_var.get().strip() or None
            d.destroy(); self._redraw()

        btns = ttk.Frame(d); btns.pack(fill="x", padx=8, pady=8)
        ttk.Button(btns, text="OK", command=ok).pack(side="right")
        ttk.Button(btns, text="Anuluj", command=d.destroy).pack(side="right", padx=6)

    # ---------- linki (połączenia graficzne) ----------
    def _open_link_dialog(self, src_el: Element):
        d = tk.Toplevel(self.root); d.title(f"Połącz: {src_el.id} → ?"); d.transient(self.root); d.grab_set()
        ttk.Label(d, text=f"Źródło: {src_el.id}").pack(anchor="w", padx=8, pady=(8,2))
        targets = [e.id for e in self._cur_room().elements if e.id != src_el.id]
        fr1 = ttk.Frame(d); fr1.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr1, text="Cel:").pack(side="left")
        tgt_var = tk.StringVar(value=(targets[0] if targets else ""))
        ttk.Combobox(fr1, textvariable=tgt_var, values=targets, state="readonly", width=16).pack(side="left", padx=6)

        fr2 = ttk.Frame(d); fr2.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr2, text="Obwód:").pack(side="left")
        cids = [c.id for c in self.project.circuits]
        circ_var = tk.StringVar(value=(cids[0] if cids else ""))
        ttk.Combobox(fr2, textvariable=circ_var, values=cids, state="readonly", width=12).pack(side="left", padx=6)

        fr3 = ttk.Frame(d); fr3.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr3, text="Notatka:").pack(side="left")
        note = ttk.Entry(fr3); note.pack(side="left", fill="x", expand=True)

        def ok():
            t = tgt_var.get().strip()
            if not t: d.destroy(); return
            self._cur_room().links.append(Link(a_id=src_el.id, b_id=t, circuit_id=(circ_var.get().strip() or None), note=note.get().strip()))
            d.destroy(); self._redraw()
        btns = ttk.Frame(d); btns.pack(fill="x", padx=8, pady=8)
        ttk.Button(btns, text="OK", command=ok).pack(side="right")
        ttk.Button(btns, text="Anuluj", command=d.destroy).pack(side="right", padx=6)

    # ---------- circuits ----------
    def _assign_leads_to_selected_circuit(self):
        sel = self.tv_circuits.selection()
        if not sel: return
        cid = sel[0]
        c = self._circuit_by_id(cid)
        if not c: return
        sel_leads = self.tv_leads.selection()
        for iid in sel_leads:
            if iid not in c.assigned_leads:
                c.assigned_leads.append(iid)
        self.project.distribution_board["free_leads"] = [l for l in self.project.distribution_board["free_leads"] if l["lead_id"] not in sel_leads]
        self._refresh_lists()

    def _circuit_by_id(self, cid: str) -> Optional[Circuit]:
        for c in self.project.circuits:
            if c.id == cid: return c
        return None

    def _add_circuit(self):
        self._open_circuit_editor()

    def _edit_circuit(self):
        sel = self.tv_circuits.selection()
        if not sel: return
        c = self._circuit_by_id(sel[0])
        if c: self._open_circuit_editor(c)

    def _del_circuit(self):
        sel = self.tv_circuits.selection()
        if not sel: return
        cid = sel[0]
        self.project.circuits = [c for c in self.project.circuits if c.id != cid]
        self._refresh_lists(); self._redraw()

    def _open_circuit_editor(self, circ: Optional[Circuit]=None):
        d = tk.Toplevel(self.root); d.title("Obwód"); d.transient(self.root); d.grab_set()
        def row(lbl, init=""):
            fr = ttk.Frame(d); fr.pack(fill="x", padx=8, pady=4)
            ttk.Label(fr, text=lbl, width=12).pack(side="left")
            e = ttk.Entry(fr); e.pack(side="left", fill="x", expand=True); e.insert(0, init)
            return e
        e_id = row("ID:", circ.id if circ else "")
        e_name = row("Nazwa:", circ.name if circ else "")
        fr = ttk.Frame(d); fr.pack(fill="x", padx=8, pady=4)
        ttk.Label(fr, text="Kolor:", width=12).pack(side="left")
        colors = list(self.settings["colors"]["circuit_palette"].keys())
        color_var = tk.StringVar(value=circ.color if circ else colors[0])
        ttk.OptionMenu(fr, color_var, color_var.get(), *colors).pack(side="left")
        e_breaker = row("Zabezp.:", circ.breaker if circ else "")
        advis = ttk.Label(d, text="", foreground="#555"); advis.pack(anchor="w", padx=8, pady=(0,8))
        def adv(*_):
            sug = ""  # sugestie zostawiamy jak były, jeśli masz w settings.json — zadziała
            advis.config(text=f"Sugestia kabla: {sug}" if sug else "")
        e_breaker.bind("<KeyRelease>", adv); adv()
        btns = ttk.Frame(d); btns.pack(fill="x", padx=8, pady=8)
        def ok():
            cid = e_id.get().strip(); nm = e_name.get().strip()
            if not cid or not nm: return
            if circ is None:
                self.project.circuits.append(Circuit(id=cid, name=nm, color=color_var.get(), breaker=e_breaker.get().strip()))
            else:
                circ.id = cid; circ.name = nm; circ.color = color_var.get(); circ.breaker = e_breaker.get().strip()
            d.destroy(); self._refresh_lists(); self._redraw()
        ttk.Button(btns, text="OK", command=ok).pack(side="right")
        ttk.Button(btns, text="Anuluj", command=d.destroy).pack(side="right", padx=6)

    # ---------- connections (lista przewodów przy elemencie) ----------
    def _open_connections_dialog(self, el: Element):
        d = tk.Toplevel(self.root); d.title(f"Połączenia: {el.id}"); d.transient(self.root); d.grab_set()

        tv = ttk.Treeview(d, columns=("cable","conductors","circuit","to_db","note"), show="headings", height=6)
        for h, w in (("cable",100),("conductors",220),("circuit",70),("to_db",70),("note",220)):
            tv.heading(h, text={"cable":"Kabel","conductors":"Żyły","circuit":"Obwód","to_db":"Do rozdz.","note":"Notatka"}[h])
            tv.column(h, width=w)
        tv.pack(fill="x", padx=8, pady=6)
        for idx,con in enumerate(el.connections):
            cons = ",".join([k for k,v in con.conductors.items() if v])
            tv.insert("", "end", iid=str(idx), values=(con.cable_type, cons, (con.circuit_id or "-"), "tak" if con.to_distribution else "nie", con.note))

        fr = ttk.Frame(d); fr.pack(fill="x", padx=8, pady=6)
        ttk.Label(fr, text="Kabel:", width=10).pack(side="left")
        types = self.settings.get("cables",{}).get("types",["2x1.5","3x1.5","3x2.5","5x2.5"])
        cable_var = tk.StringVar(value=types[0])
        ttk.Combobox(fr, textvariable=cable_var, values=types, width=10, state="readonly").pack(side="left")

        cfr = ttk.Frame(d); cfr.pack(fill="x", padx=8, pady=(0,6))
        cond_vars = {}
        def refresh_conductors():
            for w in cfr.winfo_children(): w.destroy()
            sel = cable_var.get()
            defaults = []
            if sel.startswith("2x"): defaults = ["L","N"]
            elif sel.startswith("3x"): defaults = ["L","N","PE"]
            elif sel.startswith("5x"): defaults = ["L1","L2","L3","N","PE"]
            all_keys = ["L","N","PE","L1","L2","L3"]
            for k in all_keys:
                v = tk.BooleanVar(value=(k in defaults))
                cond_vars[k]=v
                ttk.Checkbutton(cfr, text=k, variable=v).pack(side="left", padx=4)
        refresh_conductors()
        cable_var.trace_add("write", lambda *_: refresh_conductors())

        fr2 = ttk.Frame(d); fr2.pack(fill="x", padx=8, pady=6)
        to_db = tk.BooleanVar(value=True)
        ttk.Checkbutton(fr2, text="Do rozdzielnicy (wolny przewód)", variable=to_db).pack(side="left")
        ttk.Label(fr2, text="Notatka:").pack(side="left", padx=(10,4))
        note = ttk.Entry(fr2); note.pack(side="left", fill="x", expand=True)

        fr3 = ttk.Frame(d); fr3.pack(fill="x", padx=8, pady=6)
        ttk.Label(fr3, text="Obwód:", width=10).pack(side="left")
        cids = [c.id for c in self.project.circuits]
        circuit_var = tk.StringVar(value=cids[0] if cids else "")
        ttk.Combobox(fr3, textvariable=circuit_var, values=cids, width=10, state="readonly").pack(side="left")

        warn = ttk.Label(d, text="", foreground="#b58900"); warn.pack(anchor="w", padx=8)

        def add_conn():
            lim = self.settings["limits"]["max_connections_per_element"]
            if len(el.connections) >= lim:
                warn.config(text=f"Limit połączeń: {lim} (zmień w settings.json)"); return
            conductors = {k:v.get() for k,v in cond_vars.items()}
            con = Connection(cable_type=cable_var.get(), conductors=conductors, to_distribution=to_db.get(),
                             note=note.get().strip(), circuit_id=(circuit_var.get().strip() or None))
            el.connections.append(con)
            if con.to_distribution:
                lead_id = f"{el.id}:{len(el.connections)-1}"
                self.project.distribution_board["free_leads"].append({"lead_id": lead_id, "room": self._cur_room().name, "element_id": el.id, "cable_type": con.cable_type})
            d.destroy(); self._open_connections_dialog(el); self._refresh_lists(); self._redraw()

        btns = ttk.Frame(d); btns.pack(fill="x", padx=8, pady=8)
        ttk.Button(btns, text="+ Dodaj połączenie", command=add_conn).pack(side="left")
        ttk.Button(btns, text="Usuń zaznaczone", command=lambda:self._del_conn(tv, el, d)).pack(side="left", padx=6)
        ttk.Button(btns, text="Zamknij", command=d.destroy).pack(side="right")

    def _del_conn(self, tv, el: Element, dlg):
        sel = tv.selection()
        if not sel: return
        idx = int(sel[0])
        lead_id = f"{el.id}:{idx}"
        self.project.distribution_board["free_leads"] = [l for l in self.project.distribution_board["free_leads"] if l["lead_id"] != lead_id]
        if 0 <= idx < len(el.connections): del el.connections[idx]
        dlg.destroy(); self._open_connections_dialog(el); self._refresh_lists(); self._redraw()

    # ---------- pliki ----------
    def save_project(self):
        path = filedialog.asksaveasfilename(title="Zapisz projekt", defaultextension=".json", filetypes=[("JSON","*.json")])
        if not path: return
        out = {
            "version": self.project.version,
            "houses": [],
            "circuits": [asdict(c) for c in self.project.circuits],
            "distribution_board": self.project.distribution_board,
            "meta": self.project.meta
        }
        for h in self.project.houses:
            hh = {"name": h.name, "rooms": []}
            for r in h.rooms:
                rr = {
                    "name": r.name,
                    "background_image": r.background_image,
                    "elements": [],
                    # NOWE:
                    "segments": [asdict(s) for s in r.segments],
                    "links": [asdict(l) for l in r.links],
                }
                for e in r.elements:
                    rr["elements"].append({
                        "id": e.id, "type": e.type, "x": e.x, "y": e.y, "label": e.label,
                        "variant": e.variant, "power_w": e.power_w, "chain_prev": e.chain_prev,
                        "controls": e.controls, "max_current_a": e.max_current_a,
                        "connections": [asdict(c) for c in e.connections]
                    })
                hh["rooms"].append(rr)
            out["houses"].append(hh)

        with open(path,"w",encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=2)
        self.status.set(f"Zapisano: {path}")

    def load_project(self):
        path = filedialog.askopenfilename(title="Wczytaj projekt", filetypes=[("JSON","*.json")])
        if not path: return
        with open(path,"r",encoding="utf-8") as f: data = json.load(f)
        self._load_project_from_data(data)

    def _load_project_from_data(self, data):
        houses = []
        for h in data.get("houses", []):
            rooms = []
            for r in h.get("rooms", []):
                elements = []
                for e in r.get("elements", []):
                    conns = [Connection(**c) for c in e.get("connections", [])]
                    elements.append(Element(
                        id=e.get("id",""), type=e.get("type",""), x=e.get("x",0), y=e.get("y",0),
                        label=e.get("label",""), variant=e.get("variant",""),
                        power_w=e.get("power_w", None), chain_prev=e.get("chain_prev", None),
                        controls=e.get("controls", []), connections=conns, max_current_a=e.get("max_current_a", None)
                    ))
                segments = [Segment(**s) for s in r.get("segments", [])]
                links = [Link(**l) for l in r.get("links", [])]
                rooms.append(Room(
                    name=r.get("name",""), background_image=r.get("background_image",""),
                    elements=elements, segments=segments, links=links
                ))
            houses.append(House(name=h.get("name",""), rooms=rooms))
        circuits = [Circuit(**c) for c in data.get("circuits", [])]
        self.project = Project(
            version=data.get("version","0.7.0"),
            houses=houses, circuits=circuits,
            distribution_board=data.get("distribution_board", {"free_leads": []}),
            meta=data.get("meta", {})
        )
        self.current_house_idx = 0; self.current_room_idx = 0
        self._refresh_lists(); self._redraw()

    # ---------- PDF ----------
    def export_pdf(self):
        if not PIL_AVAILABLE:
            messagebox.showinfo("Brak Pillow", "Zainstaluj Pillow: pip install pillow"); return
        path = filedialog.asksaveasfilename(title="Eksport PDF", defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
        if not path: return
        W,H = 1600,1000
        if self.bg_pil is not None:
            base = self.bg_pil.copy().convert("RGB"); base = base.resize((W,H))
        else:
            base = Image.new("RGB",(W,H),"white")
        draw = ImageDraw.Draw(base)

        # SEGMENTY (układ)
        palette = {"SCIANA": (43,43,43), "OKNO": (26,115,232), "DRZWI": (165,42,42), "PRZEJSCIE": (154,205,50)}
        for s in self._cur_room().segments:
            col = palette.get(s.kind, (43,43,43))
            draw.line([s.a[0], s.a[1], s.b[0], s.b[1]], fill=col, width=4 if s.kind=="SCIANA" else 3)

        # ELEMENTY
        room = self._cur_room()
        for el in room.elements:
            r=8
            draw.ellipse([el.x-r, el.y-r, el.x+r, el.y+r], outline=(0,0,0), fill=(255,255,255))
            if el.label: draw.text((el.x+10, el.y-12), el.label, fill=(0,0,0))
            if el.connections:
                con = el.connections[0]
                x_off = el.x + 14; y_off = el.y - 8
                for k,used in con.conductors.items():
                    if used:
                        color = self._rgb(self._color_hex(k))
                        draw.rectangle([x_off, y_off, x_off+22, y_off+14], outline=(34,34,34), fill=color)
                        draw.text((x_off+5,y_off+2), k, fill=(255,255,255))
                        x_off += 26
            if el.max_current_a:
                try:
                    w = el.max_current_a * 230.0
                    draw.text((el.x+10, el.y+10), f"{el.max_current_a:.0f}A ~{int(w)}W", fill=(80,80,80))
                except: pass

        # LINKI (połączenia)
        for link in room.links:
            a = next((e for e in room.elements if e.id == link.a_id), None)
            b = next((e for e in room.elements if e.id == link.b_id), None)
            if not a or not b: continue
            col = self._rgb(self._circuit_color_hex(link.circuit_id))
            draw.line([a.x, a.y, b.x, b.y], fill=col, width=3)

        # LEGENDA OBWODÓW
        lx, ly = W-360, 40
        draw.rectangle([lx-10, ly-10, W-30, ly+430], outline=(120,120,120), fill=(245,245,245))
        draw.text((lx, ly-24), "Legenda obwodów", fill=(0,0,0))
        yy = ly
        for c in self.project.circuits:
            col = self._rgb(self.settings["colors"]["circuit_palette"].get(c.color, "#000000"))
            draw.rectangle([lx, yy, lx+26, yy+14], outline=(34,34,34), fill=col)
            draw.text((lx+34, yy), f"{c.id}  {c.name}  ({c.breaker or '-'})", fill=(0,0,0))
            yy += 18

        # LEGENDA UKŁADU
        draw.text((lx, yy+8), "Układ pokoju:", fill=(0,0,0))
        yy2 = yy + 26
        for name, col in [("Ściana", (43,43,43)), ("Okno", (26,115,232)), ("Drzwi", (165,42,42)), ("Przejście", (154,205,50))]:
            draw.line([lx, yy2, lx+28, yy2], fill=col, width=4 if name=="Ściana" else 3)
            draw.text((lx+36, yy2-8), name, fill=(0,0,0))
            yy2 += 18

        base.save(path, "PDF"); self.status.set(f"Wyeksportowano PDF: {path}")

    def _rgb(self, h):
        h=h.lstrip("#"); return tuple(int(h[i:i+2],16) for i in (0,2,4))

# ================== main ==================
def main():
    root = tk.Tk()
    app = ElektrykaApp(root)
    if os.path.exists(PROJECT_FILE_DEFAULT):
        try:
            with open(PROJECT_FILE_DEFAULT,"r",encoding="utf-8") as f:
                data = json.load(f)
            app._load_project_from_data(data)
        except Exception:
            pass
    root.mainloop()

if __name__ == "__main__":
    main()
