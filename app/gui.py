import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional
from .store import load_project, save_project
from .models import Element, Cable, Board, Circuit, Project
from .board_logic import ET_COLORS, next_symbol, validate_single_line, circuit_of_element

CANVAS_W, CANVAS_H = 1024, 576

class ElektrykaApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master.title("Domowy Elektryk — v1.1.0")
        self.pack(fill="both", expand=True)
        self.project: Project = load_project()

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

    def _build_plan_tab(self):
        left = ttk.Frame(self.tab_plan, width=220)
        left.pack(side="left", fill="y")
        mid = ttk.Frame(self.tab_plan)
        mid.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(self.tab_plan, width=220)
        right.pack(side="left", fill="y")

        # paleta elementów
        ttk.Label(left, text="Dodaj element").pack(pady=(8,4))
        self.var_et = tk.StringVar(value="GNIAZDKO")
        for et in ["GNIAZDKO","LAMPA","ROLETY","WLACZNIK","ROZDZIELNICA"]:
            ttk.Radiobutton(left, text=et.title(), value=et, variable=self.var_et).pack(anchor="w", padx=8)

        ttk.Button(left, text="Dodaj na środek", command=self._add_element_center).pack(pady=8)
        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Button(left, text="Zapisz projekt", command=self._save).pack(pady=4)

        # Canvas
        self.canvas = tk.Canvas(mid, width=CANVAS_W, height=CANVAS_H, bg="#fafafa", highlightthickness=1, highlightbackground="#ddd")
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_drop)

        # prawa lista
        ttk.Label(right, text="Elementy").pack(pady=(8,4))
        self.list_elements = tk.Listbox(right, height=24)
        self.list_elements.pack(fill="y", expand=True, padx=8)
        self.list_elements.bind("<<ListboxSelect>>", lambda e: self._focus_from_list())

        btns = ttk.Frame(right); btns.pack(pady=6)
        ttk.Button(btns, text="Połącz przewodem", command=self._start_connect).grid(row=0, column=0, padx=2)
        ttk.Button(btns, text="Usuń", command=self._delete_selected).grid(row=0, column=1, padx=2)

        self.status = ttk.Label(self.tab_plan, text="Gotowe", anchor="w")
        self.status.pack(fill="x", side="bottom")

        self.dragging_id: Optional[str] = None
        self.connect_a: Optional[str] = None
        self.temp_line = None
        self.poly_points = []

    def _build_board_tab(self):
        top = ttk.Frame(self.tab_rozdz); top.pack(fill="both", expand=True, padx=8, pady=8)
        left = ttk.Frame(top, width=280); left.pack(side="left", fill="y")
        mid = ttk.Frame(top); mid.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Rozdzielnice").pack(pady=(0,4))
        self.list_boards = tk.Listbox(left, height=10)
        self.list_boards.pack(fill="x", padx=2)
        self.list_boards.bind("<<ListboxSelect>>", lambda e: self._refresh_circuits())

        ttk.Button(left, text="Dodaj rozdzielnicę", command=self._add_board).pack(pady=6)

        # circuits
        ttk.Label(left, text="Obwody").pack(pady=(12,4))
        self.list_circuits = tk.Listbox(left, height=14)
        self.list_circuits.pack(fill="both", expand=True, padx=2)
        self.list_circuits.bind("<<ListboxSelect>>", lambda e: self._refresh_plan_colors())

        btnc = ttk.Frame(left); btnc.pack(pady=6)
        ttk.Button(btnc, text="Dodaj obwód", command=self._add_circuit).grid(row=0, column=0, padx=2)
        ttk.Button(btnc, text="Usuń obwód", command=self._del_circuit).grid(row=0, column=1, padx=2)

        # mid summary
        self.txt_info = tk.Text(mid, height=24, wrap="word")
        self.txt_info.pack(fill="both", expand=True)
        ttk.Button(mid, text="Przypisz zaznaczony obwód do wybranego elementu", command=self._assign_circuit_to_selected).pack(pady=6)

    # ---------------- Data helpers ----------------
    def _save(self):
        save_project(self.project)
        self.status.config(text="Zapisano projekt.")

    def _refresh_all(self):
        self._refresh_list_elements()
        self._draw_canvas()
        self._refresh_boards()

    def _refresh_list_elements(self):
        self.list_elements.delete(0, "end")
        for e in self.project.elements:
            self.list_elements.insert("end", f"{e.name} [{e.etype}]")

    def _refresh_boards(self):
        self.list_boards.delete(0, "end")
        for b in self.project.boards:
            self.list_boards.insert("end", f"{b.name} @ {b.location}")
        self._refresh_circuits()

    def _refresh_circuits(self):
        self.list_circuits.delete(0, "end")
        b = self._current_board()
        if not b:
            return
        for c in b.circuits:
            self.list_circuits.insert("end", f"{c.name} / {c.breaker} / {c.rcd or '—'}")
        self._render_board_info()

    def _render_board_info(self):
        b = self._current_board()
        self.txt_info.delete("1.0","end")
        if not b:
            self.txt_info.insert("end","Brak rozdzielnic.")
            return
        self.txt_info.insert("end", f"Rozdzielnica: {b.name} ({b.location})\nObwody:\n")
        for c in b.circuits:
            cnt = sum(1 for e in self.project.elements if e.circuit_id == c.id)
            self.txt_info.insert("end", f" • {c.name} — {c.breaker}, RCD {c.rcd or '—'}  | elementów: {cnt}\n")

    def _refresh_plan_colors(self):
        self._draw_canvas()

    # ---------------- Plan / Canvas ----------------
    def _draw_canvas(self):
        self.canvas.delete("all")
        # kable (kolor wg obwodu A lub B, jak brak — czarny)
        for cab in self.project.cables:
            color = "#000000"
            a = self._by_id(cab.a_element_id)
            b = self._by_id(cab.b_element_id)
            for el in (a, b):
                if not el:
                    continue
                circ = circuit_of_element(self.project, el)
                if circ and circ.color:
                    color = circ.color
                    break
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
            # zaczynamy pojedynczą trasę
            self.poly_points = [(ev.x, ev.y)]
            self.temp_line = self.canvas.create_line(ev.x, ev.y, ev.x+1, ev.y+1, width=2)
        else:
            self.dragging_id = None

    def _on_canvas_drag(self, ev):
        if self.dragging_id:
            e = self._by_id(self.dragging_id)
            if e:
                e.x, e.y = ev.x, ev.y
                self._draw_canvas()
        elif self.temp_line is not None:
            self.poly_points.append((ev.x, ev.y))
            self.canvas.coords(self.temp_line, *sum(self.poly_points, ()))

    def _on_canvas_drop(self, ev):
        if self.dragging_id:
            self.dragging_id = None
            self._save()
        elif self.temp_line is not None:
            # zakończ trasę i połącz z elementem B
            e = self._find_element_at(ev.x, ev.y)
            if self.connect_a and e:
                a = self._by_id(self.connect_a)
                if a and e.id != a.id:
                    cab = Cable(
                        id=f"CAB-{len(self.project.cables)+1:04d}",
                        a_element_id=a.id,
                        b_element_id=e.id,
                        points=validate_single_line(self.poly_points)
                    )
                    self.project.cables.append(cab)
                    self.status.config(text=f"Połączono: {a.name} → {e.name} (1 trasa).")
            if self.temp_line:
                self.canvas.delete(self.temp_line)
            self.temp_line = None
            self.poly_points = []
            self.connect_a = None
            self._draw_canvas()
            self._save()

    def _add_element_center(self):
        et = self.var_et.get()
        name = next_symbol(self.project, et)
        el = Element(id=f"EL-{len(self.project.elements)+1:04d}", etype=et, name=name, x=CANVAS_W//2, y=CANVAS_H//2)
        self.project.elements.append(el)
        self._refresh_all()
        self._save()

    def _start_connect(self):
        e = self._selected_element()
        if not e:
            messagebox.showinfo("Połącz", "Zaznacz element z listy po prawej.")
            return
        self.connect_a = e.id
        self.status.config(text=f"Wybierz na planie trasę i element docelowy (pojedyncza linia).")

    def _delete_selected(self):
        e = self._selected_element()
        if not e:
            return
        if messagebox.askyesno("Usuń", f"Usunąć {e.name}?"):
            # usuń kable z/na element
            self.project.cables = [c for c in self.project.cables if c.a_element_id != e.id and c.b_element_id != e.id]
            self.project.elements = [x for x in self.project.elements if x.id != e.id]
            self._refresh_all()
            self._save()

    def _select_in_list(self, e: Element):
        for idx, item in enumerate(self.list_elements.get(0, "end")):
            if item.startswith(e.name + " "):
                self.list_elements.selection_clear(0, "end")
                self.list_elements.selection_set(idx)
                self.list_elements.activate(idx)
                break

    def _selected_element(self) -> Optional[Element]:
        sel = self.list_elements.curselection()
        if not sel:
            return None
        name = self.list_elements.get(sel[0]).split(" ")[0]
        for e in self.project.elements:
            if e.name == name:
                return e
        return None

    def _focus_from_list(self):
        e = self._selected_element()
        if e:
            self.status.config(text=f"Zaznaczono: {e.name} [{e.etype}]")

    def _by_id(self, _id: str):
        for e in self.project.elements:
            if e.id == _id:
                return e
        return None

    # ---------------- Board tab actions ----------------
    def _current_board(self) -> Optional[Board]:
        sel = self.list_boards.curselection()
        if not sel:
            return self.project.boards[0] if self.project.boards else None
        label = self.list_boards.get(sel[0]).split(" @ ")[0]
        for b in self.project.boards:
            if b.name == label:
                return b
        return None

    def _add_board(self):
        name = simpledialog.askstring("Nowa rozdzielnica", "Nazwa (np. RG-2):")
        if not name:
            return
        self.project.boards.append(Board(id=f"BRD-{len(self.project.boards)+1:03d}", name=name, location=""))
        self._refresh_boards()
        self._save()

    def _add_circuit(self):
        b = self._current_board()
        if not b:
            messagebox.showerror("Obwody", "Najpierw dodaj rozdzielnicę.")
            return
        nm = simpledialog.askstring("Nowy obwód", "Nazwa (np. O4 Oświetlenie piętro):")
        if not nm:
            return
        br = simpledialog.askstring("Wyłącznik", "Typ wyłącznika (np. B10/B16/C20):") or "B16"
        rcd = simpledialog.askstring("RCD", "np. 30mA (puste = brak)") or None
        b.circuits.append(Circuit(id=f"CIR-{len(b.circuits)+1:03d}", name=nm, breaker=br, rcd=rcd))
        self._refresh_circuits()
        self._save()

    def _del_circuit(self):
        b = self._current_board()
        if not b:
            return
        sel = self.list_circuits.curselection()
        if not sel:
            return
        idx = sel[0]
        circ = b.circuits[idx]
        # odczep elementy
        for e in self.project.elements:
            if e.circuit_id == circ.id:
                e.circuit_id = None
        del b.circuits[idx]
        self._refresh_circuits()
        self._save()

    def _assign_circuit_to_selected(self):
        e = self._selected_element()
        if not e:
            messagebox.showinfo("Przypisz", "Zaznacz element po prawej.")
            return
        b = self._current_board()
        if not b:
            return
        sel = self.list_circuits.curselection()
        if not sel:
            messagebox.showinfo("Przypisz", "Wybierz obwód z listy.")
            return
        circ = b.circuits[sel[0]]
        e.circuit_id = circ.id
        self.status.config(text=f"Przypięto {e.name} → {circ.name}")
        self._save()

def run_app():
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    app = ElektrykaApp(root)
    root.minsize(960, 640)
    root.mainloop()
