import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Tuple
from .store import load_project, save_project
from .models import Element, Cable, Board, Circuit, Project, Module
from .board_logic import ET_COLORS, next_symbol, circuit_of_element, clamp

CANVAS_W, CANVAS_H = 1024, 576
GRID_SIZE = 40

# Paleta aparatów (typ → (domyślna etykieta, polary/pola, kolor))
MODULE_PALETTE = {
    "MAIN": ("FR", 2, "#333333"),
    "RCD":  ("30mA", 2, "#00897b"),
    "MCB":  ("B16", 1, "#455a64"),
    "RCBO": ("RCBO", 2, "#5e35b1"),
    "SPD":  ("SPD", 2, "#6d4c41"),
    "BLANK":(" ", 1, "#e0e0e0"),
}

class ElektrykaApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master.title("Domowy Elektryk — v1.2.0")
        self.pack(fill="both", expand=True)
        self.project: Project = load_project()

        self.snap_to_grid = True
        self.show_grid = True
        self.grid_size = GRID_SIZE

        self._build_ui()
        self._refresh_all()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_plan = ttk.Frame(self.nb)
        self.tab_rozdz = ttk.Frame(self.nb)
        self.nb.add(self.tab_plan, text="Plan / Mapa")
        self.nb.add(self.tab_rozdz, text="Rozdzielnica")

        self._build_plan_tab()
        self._build_board_tab()

    # ---- PLAN ----
    def _build_plan_tab(self):
        left = ttk.Frame(self.tab_plan, width=220); left.pack(side="left", fill="y")
        mid = ttk.Frame(self.tab_plan); mid.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(self.tab_plan, width=220); right.pack(side="left", fill="y")

        ttk.Label(left, text="Dodaj element").pack(pady=(8,4))
        self.var_et = tk.StringVar(value="GNIAZDKO")
        for et in ["GNIAZDKO","LAMPA","ROLETY","WLACZNIK","ROZDZIELNICA"]:
            ttk.Radiobutton(left, text=et.title(), value=et, variable=self.var_et).pack(anchor="w", padx=8)
        ttk.Button(left, text="Dodaj na środek", command=self._add_element_center).pack(pady=8)
        self.var_show_grid = tk.BooleanVar(value=self.show_grid)
        self.var_snap = tk.BooleanVar(value=self.snap_to_grid)
        ttk.Checkbutton(left, text="Pokaż siatkę", variable=self.var_show_grid,
                        command=self._toggle_grid).pack(anchor="w", padx=8)
        ttk.Checkbutton(left, text="Przyciągaj do siatki", variable=self.var_snap,
                        command=self._toggle_snap).pack(anchor="w", padx=8, pady=(0, 8))
        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Button(left, text="Zapisz projekt", command=self._save).pack(pady=4)

        self.canvas = tk.Canvas(mid, width=CANVAS_W, height=CANVAS_H, bg="#fafafa", highlightthickness=1, highlightbackground="#ddd")
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_drop)

        ttk.Label(right, text="Elementy").pack(pady=(8,4))
        self.list_elements = tk.Listbox(right, height=24); self.list_elements.pack(fill="y", expand=True, padx=8)
        self.list_elements.bind("<<ListboxSelect>>", lambda e: self._focus_from_list())
        btns = ttk.Frame(right); btns.pack(pady=6)
        ttk.Button(btns, text="Połącz przewodem", command=self._start_connect).grid(row=0, column=0, padx=2)
        ttk.Button(btns, text="Usuń", command=self._delete_selected).grid(row=0, column=1, padx=2)

        self.status = ttk.Label(self.tab_plan, text="Gotowe", anchor="w"); self.status.pack(fill="x", side="bottom")
        self._update_status()

        self.dragging_id: Optional[str] = None
        self.connect_a: Optional[str] = None
        self.temp_line = None
        self.poly_points = []

    # ---- ROZDZIELNICA (GRAFICZNA) ----
    def _build_board_tab(self):
        top = ttk.Frame(self.tab_rozdz); top.pack(fill="both", expand=True, padx=8, pady=8)
        left = ttk.Frame(top, width=260); left.pack(side="left", fill="y")
        mid = ttk.Frame(top); mid.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(top, width=260); right.pack(side="left", fill="y")

        # lista rozdzielnic
        ttk.Label(left, text="Rozdzielnice").pack(pady=(0,4))
        self.list_boards = tk.Listbox(left, height=8); self.list_boards.pack(fill="x", padx=2)
        self.list_boards.bind("<<ListboxSelect>>", lambda e: self._refresh_board_view())
        ttk.Button(left, text="Dodaj rozdzielnicę", command=self._add_board).pack(pady=6)

        # lista obwodów
        ttk.Label(left, text="Obwody").pack(pady=(12,4))
        self.list_circuits = tk.Listbox(left, height=12); self.list_circuits.pack(fill="both", expand=True, padx=2)
        ttk.Button(left, text="Dodaj obwód", command=self._add_circuit).pack(pady=6)
        ttk.Button(left, text="Usuń obwód", command=self._del_circuit).pack()

        # paleta modułów
        ttk.Label(right, text="Paleta aparatów").pack(pady=(0,4))
        self.var_mod = tk.StringVar(value="MCB")
        for k in MODULE_PALETTE.keys():
            ttk.Radiobutton(right, text=k, value=k, variable=self.var_mod).pack(anchor="w", padx=8)
        ttk.Button(right, text="Zmień etykietę…", command=self._edit_selected_module_label).pack(pady=6)
        ttk.Button(right, text="Przypisz do zazn. obwodu", command=self._assign_selected_module_to_circuit).pack(pady=2)
        ttk.Button(right, text="Usuń zaznaczony moduł", command=self._delete_selected_module).pack(pady=4)

        # Canvas rozdzielnicy
        self.board_canvas = tk.Canvas(mid, width=820, height=420, bg="#f7f7fb", highlightthickness=1, highlightbackground="#ddd")
        self.board_canvas.pack(fill="both", expand=True)
        self.board_canvas.bind("<Button-1>", self._board_click)
        self.board_canvas.bind("<B1-Motion>", self._board_drag)
        self.board_canvas.bind("<ButtonRelease-1>", self._board_drop)

        # info
        self.txt_info = tk.Text(self.tab_rozdz, height=6, wrap="word"); self.txt_info.pack(fill="x", padx=8, pady=(6,8))

        # stan
        self._drag_mod_id: Optional[str] = None  # id module wewnętrzny (Module.id)
        self._drag_offset: Tuple[int,int] = (0,0)

    # ---------------- helpers wspólne ----------------
    def _save(self):
        save_project(self.project)

    def _refresh_all(self):
        self._refresh_list_elements()
        self._draw_plan()
        self._refresh_board_lists()
        self._refresh_board_view()

    # ---- PLAN / MAPA ----
    def _refresh_list_elements(self):
        self.list_elements.delete(0, "end")
        for e in self.project.elements:
            self.list_elements.insert("end", f"{e.name} [{e.etype}]")

    def _draw_plan(self):
        self.canvas.delete("all")
        if self.show_grid and self.grid_size > 0:
            step = self.grid_size
            for x in range(0, CANVAS_W + 1, step):
                self.canvas.create_line(x, 0, x, CANVAS_H, fill="#eeeeee")
            for y in range(0, CANVAS_H + 1, step):
                self.canvas.create_line(0, y, CANVAS_W, y, fill="#eeeeee")
        # kable
        for cab in self.project.cables:
            color = "#000000"
            a = self._by_id(cab.a_element_id)
            b = self._by_id(cab.b_element_id)
            for el in (a, b):
                if not el: continue
                circ = circuit_of_element(self.project, el)
                if circ and circ.color: color = circ.color; break
            if cab.points:
                self.canvas.create_line(*sum(cab.points, ()), width=2, smooth=True, fill=color)
        # elementy
        for e in self.project.elements:
            color = ET_COLORS.get(e.etype, "#000")
            r = 18 if e.etype != "ROZDZIELNICA" else 24
            self.canvas.create_oval(e.x-r, e.y-r, e.x+r, e.y+r, fill=color, outline="")
            self.canvas.create_text(e.x, e.y, text=e.name, fill="#ffffff")

    def _find_element_at(self, x, y) -> Optional[Element]:
        for e in reversed(self.project.elements):
            r = 24 if e.etype == "ROZDZIELNICA" else 18
            if (e.x - x)**2 + (e.y - y)**2 <= r*r:
                return e
        return None

    def _on_canvas_click(self, ev):
        e = self._find_element_at(ev.x, ev.y)
        if e:
            self.dragging_id = e.id
            self._select_in_list(e)
        elif self.connect_a and self.temp_line is None:
            self.poly_points = [(ev.x, ev.y)]
            self.temp_line = self.canvas.create_line(ev.x, ev.y, ev.x+1, ev.y+1, width=2)
        else:
            self.dragging_id = None

    def _on_canvas_drag(self, ev):
        if self.dragging_id:
            e = self._by_id(self.dragging_id)
            if e:
                e.x, e.y = self._snap(ev.x, ev.y)
                self._draw_plan()
        elif self.temp_line is not None:
            self.poly_points.append((ev.x, ev.y))
            self.canvas.coords(self.temp_line, *sum(self.poly_points, ()))

    def _on_canvas_drop(self, ev):
        if self.dragging_id:
            moving_id = self.dragging_id
            self.dragging_id = None
            if self.snap_to_grid:
                e = self._by_id(moving_id)
                if e:
                    e.x, e.y = self._snap(e.x, e.y)
            self._draw_plan()
            self._save()
        elif self.temp_line is not None:
            e = self._find_element_at(ev.x, ev.y)
            if self.connect_a and e:
                a = self._by_id(self.connect_a)
                if a and e.id != a.id:
                    self.project.cables.append(Cable(
                        id=f"CAB-{len(self.project.cables)+1:04d}",
                        a_element_id=a.id, b_element_id=e.id, points=self.poly_points[:]
                    ))
            if self.temp_line:
                self.canvas.delete(self.temp_line)
            self.temp_line = None
            self.poly_points = []
            self.connect_a = None
            self._draw_plan(); self._save()

    def _add_element_center(self):
        et = self.var_et.get()
        name = next_symbol(self.project, et)
        el = Element(id=f"EL-{len(self.project.elements)+1:04d}", etype=et, name=name, x=CANVAS_W//2, y=CANVAS_H//2)
        el.x, el.y = self._snap(el.x, el.y)
        self.project.elements.append(el)
        self._refresh_all(); self._save()

    def _start_connect(self):
        e = self._selected_element()
        if not e:
            messagebox.showinfo("Połącz", "Zaznacz element po prawej.")
            return
        self.connect_a = e.id

    def _delete_selected(self):
        e = self._selected_element()
        if not e: return
        if messagebox.askyesno("Usuń", f"Usunąć {e.name}?"):
            self.project.cables = [c for c in self.project.cables if c.a_element_id!=e.id and c.b_element_id!=e.id]
            self.project.elements = [x for x in self.project.elements if x.id!=e.id]
            self._refresh_all(); self._save()

    def _select_in_list(self, e: Element):
        for idx, item in enumerate(self.list_elements.get(0, "end")):
            if item.startswith(e.name+" "):
                self.list_elements.selection_clear(0,"end")
                self.list_elements.selection_set(idx); self.list_elements.activate(idx); break

    def _selected_element(self) -> Optional[Element]:
        sel = self.list_elements.curselection()
        if not sel: return None
        name = self.list_elements.get(sel[0]).split(" ")[0]
        for e in self.project.elements:
            if e.name == name: return e
        return None

    def _snap(self, x: int, y: int) -> Tuple[int, int]:
        if not self.snap_to_grid or self.grid_size <= 0:
            return x, y
        gx = round(x / self.grid_size) * self.grid_size
        gy = round(y / self.grid_size) * self.grid_size
        return int(gx), int(gy)

    def _toggle_grid(self):
        self.show_grid = bool(self.var_show_grid.get())
        self._draw_plan()
        self._update_status()

    def _toggle_snap(self):
        self.snap_to_grid = bool(self.var_snap.get())
        if self.snap_to_grid:
            for e in self.project.elements:
                e.x, e.y = self._snap(e.x, e.y)
            self._draw_plan()
            self._save()
        self._update_status()

    def _update_status(self, text: Optional[str] = None):
        if not hasattr(self, "status"):
            return
        if text is None:
            text = f"Siatka: {'ON' if self.show_grid else 'OFF'}  |  Przyciąganie: {'ON' if self.snap_to_grid else 'OFF'}"
        self.status.config(text=text)

    def _by_id(self, _id: str):
        for e in self.project.elements:
            if e.id == _id: return e
        return None

    # ---- ROZDZIELNICA: LISTY + CANVAS ----
    def _current_board(self) -> Optional[Board]:
        sel = self.list_boards.curselection()
        if not sel:
            return self.project.boards[0] if self.project.boards else None
        label = self.list_boards.get(sel[0]).split(" @ ")[0]
        for b in self.project.boards:
            if b.name == label: return b
        return None

    def _refresh_board_lists(self):
        self.list_boards.delete(0,"end")
        for b in self.project.boards:
            self.list_boards.insert("end", f"{b.name} @ {b.location}")
        self.list_circuits.delete(0,"end")
        b = self._current_board()
        if not b: return
        for c in b.circuits:
            self.list_circuits.insert("end", f"{c.name} / {c.breaker} / {c.rcd or '—'}")

    def _refresh_board_view(self):
        self._refresh_board_lists()
        b = self._current_board()
        self.board_canvas.delete("all")
        self.txt_info.delete("1.0","end")
        if not b:
            self.txt_info.insert("end","Brak rozdzielnic."); return
        # siatka (pola 24px)
        sz = 24
        pad = 20
        W = b.cols*sz + pad*2
        H = b.rows*sz + pad*2
        self.board_canvas.config(scrollregion=(0,0,W,H))
        # tło i kratka
        self.board_canvas.create_rectangle(pad, pad, pad+b.cols*sz, pad+b.rows*sz, fill="#ffffff", outline="#cfd8dc")
        for r in range(b.rows+1):
            y = pad + r*sz
            self.board_canvas.create_line(pad, y, pad+b.cols*sz, y, fill="#eceff1")
        for c in range(b.cols+1):
            x = pad + c*sz
            self.board_canvas.create_line(x, pad, x, pad+b.rows*sz, fill="#eceff1")
        # moduły
        for m in b.modules:
            self._draw_module(m, pad, sz)
        # info
        self.txt_info.insert("end", f"{b.name} ({b.location})  |  wiersze: {b.rows}, kolumny: {b.cols}\n")
        for c in b.circuits:
            self.txt_info.insert("end", f" • {c.name} — {c.breaker}, RCD {c.rcd or '—'}\n")

    def _draw_module(self, m: Module, pad: int, sz: int):
        x1 = pad + m.col*sz
        y1 = pad + m.row*sz
        x2 = x1 + m.poles*sz
        y2 = y1 + sz
        rect = self.board_canvas.create_rectangle(x1, y1, x2, y2, fill=m.color, outline="#455a64")
        txt = self.board_canvas.create_text((x1+x2)//2, (y1+y2)//2, text=m.label, fill="#ffffff")
        # zapisz mapping id → canvas items
        self.board_canvas.tag_bind(rect, "<Button-1>", lambda e, mid=m.id: self._start_drag_module(e, mid))
        self.board_canvas.tag_bind(txt,  "<Button-1>", lambda e, mid=m.id: self._start_drag_module(e, mid))
        self.board_canvas.addtag_withtag(f"mod-{m.id}", rect)
        self.board_canvas.addtag_withtag(f"mod-{m.id}", txt)

    # --- akcje rozdzielnicy ---
    def _add_board(self):
        name = simpledialog.askstring("Nowa rozdzielnica", "Nazwa (np. RG-2):")
        if not name: return
        self.project.boards.append(Board(id=f"BRD-{len(self.project.boards)+1:03d}", name=name, location=""))
        self._refresh_board_view(); self._save()

    def _add_circuit(self):
        b = self._current_board()
        if not b: return
        nm = simpledialog.askstring("Nowy obwód", "Nazwa (np. O4 Oświetlenie piętro):")
        if not nm: return
        br = simpledialog.askstring("Wyłącznik", "Typ (B10/B16/C20):") or "B16"
        rcd = simpledialog.askstring("RCD", "np. 30mA (puste = brak)") or None
        b.circuits.append(Circuit(id=f"CIR-{len(b.circuits)+1:03d}", name=nm, breaker=br, rcd=rcd))
        self._refresh_board_view(); self._save()

    def _del_circuit(self):
        b = self._current_board()
        if not b: return
        sel = self.list_circuits.curselection()
        if not sel: return
        circ = b.circuits[sel[0]]
        # odpinamy moduły przypięte do tego obwodu
        for m in b.modules:
            if m.circuit_id == circ.id: m.circuit_id = None
        del b.circuits[sel[0]]
        self._refresh_board_view(); self._save()

    # --- Canvas: dodawanie/drag/usuwanie modułów ---
    def _board_click(self, ev):
        b = self._current_board()
        if not b: return
        # kliknięcie w puste pole = dodanie modułu z palety
        pad, sz = 20, 24
        col = clamp((ev.x - pad)//sz, 0, b.cols-1)
        row = clamp((ev.y - pad)//sz, 0, b.rows-1)
        kind = self.var_mod.get()
        label, poles, color = MODULE_PALETTE[kind]
        # upewnij się, że mieści się na szerokość
        col = min(col, b.cols - poles)
        m = Module(id=f"MOD-{len(b.modules)+1:04d}", kind=kind, label=label, poles=poles, row=row, col=col, color=color)
        b.modules.append(m)
        self._refresh_board_view(); self._save()

    def _start_drag_module(self, ev, mid: str):
        self._drag_mod_id = mid
        self._drag_offset = (ev.x, ev.y)

    def _board_drag(self, ev):
        if not self._drag_mod_id: return

    def _board_drop(self, ev):
        if not self._drag_mod_id: return
        b = self._current_board()
        if not b: return
        pad, sz = 20, 24
        col = clamp((ev.x - pad)//sz, 0, b.cols-1)
        row = clamp((ev.y - pad)//sz, 0, b.rows-1)
        # znajdź moduł
        for m in b.modules:
            if m.id == self._drag_mod_id:
                col = min(col, b.cols - m.poles)
                m.col, m.row = col, row
                break
        self._drag_mod_id = None
        self._refresh_board_view(); self._save()

    def _delete_selected_module(self):
        b = self._current_board()
        if not b: return
        # wybór po wskazaniu współrzędnych (dialog)
        mid = simpledialog.askstring("Usuń moduł", "Podaj ID modułu (np. MOD-0001). Pokaż ID: Menu → Info panel.")
        if not mid: return
        b.modules = [m for m in b.modules if m.id != mid]
        self._refresh_board_view(); self._save()

    def _edit_selected_module_label(self):
        b = self._current_board()
        if not b: return
        mid = simpledialog.askstring("Etykieta", "ID modułu do zmiany etykiety:")
        if not mid: return
        m = next((x for x in b.modules if x.id == mid), None)
        if not m: messagebox.showerror("Etykieta","Nie znaleziono modułu."); return
        lbl = simpledialog.askstring("Etykieta", f"Aktualna: {m.label}\nNowa etykieta:")
        if not lbl: return
        m.label = lbl
        self._refresh_board_view(); self._save()

    def _assign_selected_module_to_circuit(self):
        b = self._current_board()
        if not b: return
        mid = simpledialog.askstring("Przypisz moduł", "ID modułu:")
        if not mid: return
        sel = self.list_circuits.curselection()
        if not sel:
            messagebox.showinfo("Przypisz", "Wybierz obwód z listy po lewej."); return
        circ = b.circuits[sel[0]]
        m = next((x for x in b.modules if x.id == mid), None)
        if not m: messagebox.showerror("Przypisz","Nie znaleziono modułu."); return
        m.circuit_id = circ.id
        # jeśli to MCB — nadaj kolor obwodu dla spójności
        if m.kind in ("MCB","RCBO") and circ.color:
            m.color = circ.color
            if circ.breaker: m.label = f"{circ.breaker} {circ.name.split()[0]}"
        self._refresh_board_view(); self._save()

    # --- drobne ---
    def _focus_from_list(self): pass

def run_app():
    root = tk.Tk()
    style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    app = ElektrykaApp(root)
    root.minsize(1100, 720)
    root.mainloop()

# ⏹ KONIEC KODU
