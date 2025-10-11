# Domowy Elektryk v1.9.0 — JSON persist + twarde reguły RCD + L1/L2/L3 + autosave on exit
# Autor: ChatGPT Codex — 2025-10-08

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict
import json, os

# ------------ GRAFIKA / STAŁE ------------
BASE_MOD_W = 48
BASE_MOD_H = BASE_MOD_W * 4
BASE_ROW_GAP = 12
BASE_PAD = 24
GROUP_COLORS = ["#2563eb","#16a34a","#f59e0b","#ef4444","#9333ea","#0ea5e9","#84cc16","#fb7185"]
PHASE_LABELS = ["L1","L2","L3"]

# ------------ TYPY APARATÓW ------------
MODULE_TYPES = [
    ("FR - Wyłącznik główny", "FR", 2),
    ("RCD 30mA - Różnicówka", "RCD", 2),
    ("MCB B10", "B10", 1),
    ("MCB B16", "B16", 1),
    ("MCB C20", "C20", 1),
    ("SPD - Ochronnik", "SPD", 2),
    ("PSU 24V - Zasilacz", "PSU", 3),
    ("PLC - Sterownik", "PLC", 4),
    ("RELAY - Przekaźnik", "RELAY", 2),
    ("PUSTE MIEJSCE", "", 1),
]
def is_mcb(code:str)->bool:
    return bool(code) and (code.startswith("B") or code.startswith("C"))

# ------------ HEURYSTYKI ------------
WEIGHTS_DEFAULT = {"gniazd":2, "agd":3, "łazien":3, "lazien":3, "kuch":3, "oświet":1, "oswiet":1, "garaż":2, "garaz":2}
WEIGHT_FALLBACK = 2
MAX_MCB_PER_RCD_DEFAULT = 6
KITCHEN_PER_RCD_LIMIT_DEFAULT = 3  # maximum kitchen circuits allowed per RCD

# ------------ MODELE ------------
@dataclass
class Module:
    row: int
    col: int
    width: int
    code: str
    label: str
    circuit_id: Optional[str] = None

@dataclass
class Circuit:
    cid: str
    name: str
    breaker: str
    assigned: bool = False

# ------------ APP ------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Domowy Elektryk v1.9.0 — Plan • Rozdzielnica • Synchronizacja")
        self.geometry("1400x820"); self.minsize(1200,700)

        # stan
        self.rows, self.cols = 2, 12
        self.modules: List[Module] = []
        self.circuits: List[Circuit] = []
        self.rcd_groups: Dict[int, List[int]] = {}
        self.rcd_limit = MAX_MCB_PER_RCD_DEFAULT
        self.kitchen_limit = KITCHEN_PER_RCD_LIMIT_DEFAULT
        self.scale = 1.0
        self.dirty = False  # zmieniono projekt?

        # ścieżka projektu
        self.project_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.json")

        # UI
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_exit)  # autosave on exit
        self._build_ui()

        # spróbuj wczytać projekt
        if self._load_project():
            self._log_sync("Wczytano projekt z JSON.")
        else:
            # seed
            self.circuits = [
                Circuit("O1","O1 Gniazda", "B16"),
                Circuit("O2","O2 Oświetlenie", "B10"),
                Circuit("O3","O3 Rolety", "B16"),
            ]
            self._mark_dirty()
        self._refresh_all()

    # ---------- UI ----------
    def _build_ui(self):
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Nowy", command=self._new_project)
        filem.add_command(label="Otwórz…", command=self._open_project_dialog)
        filem.add_command(label="Zapisz", command=self._save_project)
        filem.add_command(label="Zapisz jako…", command=self._save_as_dialog)
        filem.add_separator()
        filem.add_command(label="Wyjście", command=self._on_exit)
        menubar.add_cascade(label="Plik", menu=filem)
        self.config(menu=menubar)

        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True)

        # Plan
        self.tab_plan = ttk.Frame(self.nb); self.nb.add(self.tab_plan, text="Plan / Mapa")
        self._build_plan_tab()

        # Rozdzielnica
        self.tab_board = ttk.Frame(self.nb); self.nb.add(self.tab_board, text="Rozdzielnica")
        self._build_board_tab()

        # Sync
        self.tab_sync = ttk.Frame(self.nb); self.nb.add(self.tab_sync, text="Synchronizacja")
        self._build_sync_tab()

    # ---------- PLAN (simple demo) ----------
    def _build_plan_tab(self):
        wrap = ttk.Frame(self.tab_plan); wrap.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(wrap, width=260); left.pack(side="left", fill="y")
        mid = ttk.Frame(wrap); mid.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Elementy (demo)").pack(pady=(0,6))
        self.lb_elems = tk.Listbox(left, height=16)
        for nm in ["RG-1 (Rozdzielnica)","G-01 (Gniazdo)","L-01 (Lampa)","W-01 (Włącznik)"]:
            self.lb_elems.insert("end", nm)
        self.lb_elems.pack(fill="y", padx=4)

        self.plan_canvas = tk.Canvas(mid, bg="#fafafa", highlightthickness=1, highlightbackground="#ccc")
        self.plan_canvas.pack(fill="both", expand=True)
        # prosta ilustracja
        self.plan_canvas.create_line(80,300,380,300, width=2, fill="#ffffff")
        self.plan_canvas.create_line(480,320,620,160, width=2, fill="#ffffff", dash=(4,4))
        for (x,y,label) in [(80,300,"RG"),(380,300,"G-01"),(620,160,"L-01"),(480,320,"W-01")]:
            r=18
            self.plan_canvas.create_oval(x-r,y-r,x+r,y+r, fill="#303134", outline="")
            self.plan_canvas.create_text(x,y,text=label, fill="#fff")

    # ---------- ROZDZIELNICA ----------
    def _build_board_tab(self):
        top = ttk.Frame(self.tab_board); top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Układ:", font=("Segoe UI",10,"bold")).pack(side="left")
        self.cmb_layout = ttk.Combobox(top, state="readonly", values=["2×12","3×18","1×12","własny…"], width=8)
        self.cmb_layout.current(0); self.cmb_layout.pack(side="left", padx=6)
        ttk.Button(top, text="Ustaw", command=self._apply_layout).pack(side="left")

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Button(top, text="Eksport CSV (BOM)", command=self.export_csv).pack(side="left")
        ttk.Button(top, text="Zapisz PNG (front)", command=self.save_png).pack(side="left", padx=6)
        ttk.Button(top, text="Wyczyść", command=self._clear_board).pack(side="left", padx=6)

        # reguły
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Label(top, text="Limit MCB/RCD:").pack(side="left")
        self.spn_limit = tk.Spinbox(top, from_=2, to=16, width=5); self.spn_limit.delete(0,"end"); self.spn_limit.insert(0, str(MAX_MCB_PER_RCD_DEFAULT)); self.spn_limit.pack(side="left", padx=(6,10))
        ttk.Label(top, text="Kuchnia max MCB/RCD:").pack(side="left")
        self.spn_kitchen = tk.Spinbox(top, from_=1, to=10, width=5); self.spn_kitchen.delete(0,"end"); self.spn_kitchen.insert(0, str(KITCHEN_PER_RCD_LIMIT_DEFAULT)); self.spn_kitchen.pack(side="left", padx=(6,0))
        ttk.Button(top, text="Analizuj i sugeruj", command=self.analyze_grouping).pack(side="left", padx=8)

        mid = ttk.Frame(self.tab_board); mid.pack(fill="both", expand=True, padx=10, pady=(0,10))
        self.board_canvas = tk.Canvas(mid, bg="#f2f3f5", highlightthickness=1, highlightbackground="#9aa0a6")
        self.board_canvas.pack(side="left", fill="both", expand=True)
        self.board_canvas.bind("<Button-1>", self._click_board)
        self.board_canvas.bind("<Motion>", self._on_motion_board)
        self.board_canvas.bind("<Leave>", lambda e: self._clear_tooltip())

        right = ttk.Frame(mid, width=320); right.pack(side="left", fill="y", padx=(10,0))
        ttk.Label(right, text="Wynik analizy RCD / Fazy", font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.out_board = tk.Text(right, height=26, wrap="word"); self.out_board.pack(fill="both", expand=True, pady=(6,0))

    # ---------- SYNC ----------
    def _build_sync_tab(self):
        wrap = ttk.Frame(self.tab_sync); wrap.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(wrap, width=360); left.pack(side="left", fill="y")
        mid = ttk.Frame(wrap); mid.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Obwody (logiczna lista)", font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.lb_circuits = tk.Listbox(left, height=18); self.lb_circuits.pack(fill="both", expand=True, pady=6)
        btns = ttk.Frame(left); btns.pack(fill="x")
        ttk.Button(btns, text="➕ Dodaj obwód", command=self.add_circuit).pack(side="left")
        ttk.Button(btns, text="🗑 Usuń", command=self.del_circuit).pack(side="left", padx=6)

        ops = ttk.Frame(left); ops.pack(fill="x", pady=(12,0))
        ttk.Button(ops, text="🔗 Auto-przypnij wolne obwody → MCB", command=self.autopin_free_circuits).pack(fill="x")

        self.out_sync = tk.Text(mid, height=28, wrap="word")
        self.out_sync.pack(fill="both", expand=True)
        self._log_sync("Wskazówka: Dodawaj obwody i użyj „Auto-przypnij wolne obwody”, aby wstawić brakujące MCB.")

    # ---------- RYSOWANIE ROZDZIELNICY ----------
    def draw_board(self):
        c = self.board_canvas; c.delete("all")
        MOD_W = BASE_MOD_W * self.scale; MOD_H = BASE_MOD_H * self.scale
        ROW_GAP = BASE_ROW_GAP * self.scale; PAD = BASE_PAD * self.scale

        W = self.cols*MOD_W + 2*PAD
        H = self.rows*MOD_H + (self.rows-1)*ROW_GAP + 2*PAD
        c.config(scrollregion=(0,0,W,H))

        # Rama
        c.create_rectangle(PAD-12*self.scale, PAD-12*self.scale,
                           PAD + self.cols*MOD_W + 12*self.scale,
                           PAD + self.rows*MOD_H + (self.rows-1)*ROW_GAP + 12*self.scale,
                           outline="#6b7280", width=max(1,self.scale), fill="#e5e7eb")

        # Siatka + szyny DIN
        for r in range(self.rows):
            y_top = PAD + r*(MOD_H + ROW_GAP)
            c.create_rectangle(PAD, y_top + 10*self.scale, PAD + self.cols*MOD_W, y_top + 14*self.scale, fill="#cbd5e1", outline="")
            for cc in range(self.cols):
                x1 = PAD + cc*MOD_W; y1 = y_top; x2 = x1 + MOD_W; y2 = y1 + MOD_H
                tag = f"cell-{r}-{cc}"
                c.create_rectangle(x1, y1, x2, y2, outline="#111", fill="#ffffff", tags=tag)
                c.tag_bind(tag, "<Button-1>", lambda e, rr=r, cc=cc: self._cell_clicked(rr, cc))
                if r == self.rows-1:
                    c.create_text(x1 + MOD_W/2, y2 + 12*self.scale, text=str(cc+1), fill="#374151", font=("Segoe UI", int(8*self.scale)))

        # Szyny N/PE z prawej
        right_x = PAD + self.cols*MOD_W + 18*self.scale
        top_y = PAD
        c.create_rectangle(right_x, top_y, right_x+12*self.scale, top_y + self.rows*MOD_H + (self.rows-1)*ROW_GAP, fill="#3b82f6", outline="#1d4ed8")
        c.create_text(right_x+6*self.scale, top_y-10*self.scale, text="N", fill="#1d4ed8", font=("Segoe UI", int(10*self.scale)))
        right_x2 = right_x + 22*self.scale
        c.create_rectangle(right_x2, top_y, right_x2+12*self.scale, top_y + self.rows*MOD_H + (self.rows-1)*ROW_GAP, fill="#84cc16", outline="#166534")
        c.create_text(right_x2+6*self.scale, top_y-10*self.scale, text="PE", fill="#166534", font=("Segoe UI", int(10*self.scale)))

        # Moduły
        for idx, m in enumerate(self.modules):
            x1,y1,x2,y2 = self._m_rect(m)
            c.create_rectangle(x1+1, y1+1, x2-1, y2-1, fill="#ffffff", outline="#111")
            c.create_rectangle(x1+1, y1+1, x2-1, y1+12*self.scale, fill="#d1d5db", outline="#d1d5db")
            c.create_text((x1+x2)//2, (y1+y2)//2, text=(m.label or m.code or " "), font=("Segoe UI", int(10*self.scale)), fill="#111")

            tag = f"mod-{idx}"
            c.create_rectangle(x1+1, y1+1, x2-1, y2-1, outline="", fill="", tags=tag)
            c.tag_bind(tag, "<Button-1>", lambda e, i=idx: self._edit_module(i))
            c.tag_bind(tag, "<Motion>", lambda e, i=idx: self._show_tooltip_mod(i, e.x, e.y))

            # mostki do N/PE dla MCB
            if is_mcb(m.code):
                midx = (x1+x2)/2
                c.create_line(midx, y2, midx, y2+10*self.scale, fill="#111", width=max(1,int(1*self.scale)))
                c.create_line(midx, y2+10*self.scale, right_x,  y2+10*self.scale, fill="#3b82f6")
                c.create_line(midx, y2+16*self.scale, right_x2, y2+16*self.scale, fill="#84cc16")

        # Belki RCD + fazy
        self._draw_rcd_groups_with_phases()

    def _m_rect(self, m: Module)->Tuple[float,float,float,float]:
        MOD_W = BASE_MOD_W * self.scale; MOD_H = BASE_MOD_H * self.scale
        ROW_GAP = BASE_ROW_GAP * self.scale; PAD = BASE_PAD * self.scale
        x1 = PAD + m.col * MOD_W; y1 = PAD + m.row * (MOD_H + ROW_GAP)
        x2 = x1 + m.width * MOD_W; y2 = y1 + MOD_H
        return x1,y1,x2,y2

    # ---------- INTERAKCJA ROZDZIELNICY ----------
    def _cell_clicked(self, row:int, col:int):
        hit = self._find_module_starting_at(row,col)
        if hit is not None: self._edit_module(hit); return
        self._insert_dialog(row,col)

    def _insert_dialog(self, row:int, col:int):
        top = tk.Toplevel(self); top.title(f"Dodaj aparat r{row+1}/c{col+1}"); top.grab_set()
        frm = ttk.Frame(top); frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Typ aparatu:").grid(row=0,column=0,sticky="w")
        cmb = ttk.Combobox(frm, state="readonly", width=28, values=[n for n,_,_ in MODULE_TYPES]); cmb.current(2)
        cmb.grid(row=0,column=1,sticky="ew",pady=4)

        ttk.Label(frm, text="Etykieta:").grid(row=1,column=0,sticky="w")
        ent_label = ttk.Entry(frm, width=28); ent_label.grid(row=1,column=1,sticky="ew",pady=4)

        ttk.Label(frm, text="Szerokość (poles):").grid(row=2,column=0,sticky="w")
        spn = tk.Spinbox(frm, from_=1, to=self.cols, width=5); spn.grid(row=2,column=1,sticky="w",pady=4)

        ttk.Label(frm, text="Przypisz obwód (opc.):").grid(row=3,column=0,sticky="w")
        cids = ["—"] + [c.cid for c in self.circuits]
        cmb_cid = ttk.Combobox(frm, state="readonly", values=cids, width=10); cmb_cid.current(0)
        cmb_cid.grid(row=3,column=1,sticky="w",pady=4)

        def prefill(*_):
            _, code, poles = MODULE_TYPES[cmb.current()]
            if not ent_label.get(): ent_label.insert(0, code)
            spn.delete(0,"end"); spn.insert(0, str(poles))
        prefill(); cmb.bind("<<ComboboxSelected>>", prefill)

        def ok():
            _, code, pdef = MODULE_TYPES[cmb.current()]
            label = ent_label.get().strip() or code
            try: width = int(spn.get())
            except: width = pdef
            width = max(1, min(width, self.cols))
            if col + width > self.cols: width = self.cols - col
            if self._overlaps(row,col,width):
                messagebox.showerror("Kolizja","Te pola są już zajęte."); return
            circuit_id = None if cmb_cid.get()=="—" else cmb_cid.get()
            self.modules.append(Module(row,col,width,code,label,circuit_id))
            if circuit_id: self._mark_circuit_assigned(circuit_id)
            self.rcd_groups.clear(); self._mark_dirty()
            self.draw_board(); self._report_board(); top.destroy()
        ttk.Button(frm, text="OK", command=ok).grid(row=4,column=0,pady=(10,0))
        ttk.Button(frm, text="Anuluj", command=top.destroy).grid(row=4,column=1,pady=(10,0))

    def _edit_module(self, idx:int):
        m = self.modules[idx]
        top = tk.Toplevel(self); top.title(f"Edycja: {m.label or m.code}"); top.grab_set()
        frm = ttk.Frame(top); frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Typ aparatu:").grid(row=0,column=0,sticky="w")
        cmb = ttk.Combobox(frm, state="readonly", width=28, values=[n for n,_,_ in MODULE_TYPES])
        cur=0
        for i,(_,code,_) in enumerate(MODULE_TYPES):
            if code == m.code: cur=i; break
        cmb.current(cur); cmb.grid(row=0,column=1,sticky="ew",pady=4)

        ttk.Label(frm, text="Etykieta:").grid(row=1,column=0,sticky="w")
        ent = ttk.Entry(frm, width=28); ent.insert(0, m.label); ent.grid(row=1,column=1,sticky="ew",pady=4)

        ttk.Label(frm, text="Szerokość (poles):").grid(row=2,column=0,sticky="w")
        spn = tk.Spinbox(frm, from_=1, to=self.cols, width=5); spn.delete(0,"end"); spn.insert(0, str(m.width))
        spn.grid(row=2,column=1,sticky="w",pady=4)

        ttk.Label(frm, text="Obwód (opc.):").grid(row=3,column=0,sticky="w")
        cids = ["—"] + [c.cid for c in self.circuits]
        cmb_cid = ttk.Combobox(frm, state="readonly", values=cids, width=10)
        cmb_cid.current(0 if not m.circuit_id else cids.index(m.circuit_id))
        cmb_cid.grid(row=3,column=1,sticky="w",pady=4)

        def save():
            _, code, _ = MODULE_TYPES[cmb.current()]
            label = ent.get().strip() or code
            try: width = int(spn.get())
            except: width = m.width
            width = max(1, min(width, self.cols))
            if m.col + width > self.cols: width = self.cols - m.col
            if self._overlaps(m.row,m.col,width,ignore_idx=idx):
                messagebox.showerror("Kolizja","Zmiana szerokości nachodzi na inny moduł."); return
            m.code, m.label, m.width = code, label, width
            new_cid = None if cmb_cid.get()=="—" else cmb_cid.get()
            m.circuit_id = new_cid
            self._recalc_circuit_assignments()
            self.rcd_groups.clear(); self._mark_dirty()
            self.draw_board(); self._report_board(); top.destroy()

        def delete():
            if messagebox.askyesno("Usuń", f"Usunąć „{m.label or m.code}”?"):
                del self.modules[idx]
                self._recalc_circuit_assignments()
                self.rcd_groups.clear(); self._mark_dirty()
                self.draw_board(); self._report_board(); top.destroy()

        ttk.Button(frm, text="Zapisz", command=save).grid(row=4,column=0,pady=(10,0))
        ttk.Button(frm, text="Usuń", command=delete).grid(row=4,column=1,pady=(10,0))

    # ---------- ANALIZA / RCD + TWARDER REGUŁY + FAZY ----------
    def analyze_grouping(self):
        try: self.rcd_limit = int(self.spn_limit.get())
        except: self.rcd_limit = MAX_MCB_PER_RCD_DEFAULT
        try: self.kitchen_limit = int(self.spn_kitchen.get())
        except: self.kitchen_limit = KITCHEN_PER_RCD_LIMIT_DEFAULT

        rcd_idx = [i for i,m in enumerate(self.modules) if m.code=="RCD"]
        mcb_idx = [i for i,m in enumerate(self.modules) if is_mcb(m.code)]
        self.rcd_groups.clear()
        out = []

        if not rcd_idx:
            need = max(1, (len(mcb_idx)+self.rcd_limit-1)//self.rcd_limit) if mcb_idx else 1
            out.append(f"⚠️ Brak RCD. Sugerowane: {need} (limit {self.rcd_limit} MCB/RCD).")
            self._board_log("\n".join(out)); self.draw_board(); return

        # inicjuj grupy
        for r in rcd_idx: self.rcd_groups[r] = []
        weights = {i: self._estimate_weight(self.modules[i]) for i in mcb_idx}
        sums = {r:0 for r in rcd_idx}; counts = {r:0 for r in rcd_idx}
        kitchen_counts = {r:0 for r in rcd_idx}  # reguła kuchnia
        used_rcd_exclusive = set()

        # 1) Wyłap łazienkę → osobny RCD
        bath_mcb = [i for i in mcb_idx if self._is_bath(self.modules[i])]
        for idx in bath_mcb:
            chosen = self._pick_free_rcd_for_exclusive(rcd_idx, used_rcd_exclusive, self.modules[idx])
            if chosen is None:
                out.append("⚠️ Brak wolnego RCD dla łazienki — rozważ dodanie RCD.")
                continue
            self.rcd_groups[chosen].append(idx); used_rcd_exclusive.add(chosen)
            sums[chosen] += weights[idx]; counts[chosen] += 1

        # pozostałe MCB
        rest_mcb = [i for i in mcb_idx if i not in sum(self.rcd_groups.values(), [])]
        # sort wg wagi i bliskości
        rest_mcb.sort(key=lambda k: (-weights[k], self._nearest_rcd_distance(k, rcd_idx)))

        for i in rest_mcb:
            mods = self.modules
            is_kitchen = self._is_kitchen(mods[i])
            # kandydaci wg sumy i dystansu
            candidates = sorted(rcd_idx, key=lambda r: (sums[r], self._distance(mods[i], mods[r])))
            chosen = None
            for r in candidates:
                if counts[r] >= self.rcd_limit: continue
                if r in used_rcd_exclusive:  # ten rcd jest już "łazienkowy"
                    continue
                if is_kitchen and kitchen_counts[r] >= self.kitchen_limit:
                    continue
                chosen = r; break
            if chosen is None:
                # wszystko pełne → weź najbliższy nie-ekskluzywny
                free = [r for r in rcd_idx if r not in used_rcd_exclusive]
                if free:
                    chosen = min(free, key=lambda r: self._distance(mods[i], mods[r]))
                else:
                    chosen = min(rcd_idx, key=lambda r: self._distance(mods[i], mods[r]))
            self.rcd_groups[chosen].append(i)
            sums[chosen] += weights[i]; counts[chosen] += 1
            if is_kitchen: kitchen_counts[chosen] += 1

        # Przydział faz L1/L2/L3 do grup → balans sum
        phase_of_group = self._assign_phases_to_groups(sums)

        # raport
        for r in rcd_idx:
            lst = self.rcd_groups[r]
            total = sum(weights[i] for i in lst)
            label_rcd = self.modules[r].label or "RCD 30mA"
            items = ", ".join(self.modules[i].label or self.modules[i].code for i in lst) or "—"
            phase = phase_of_group.get(r, "L1")
            out.append(f"🟢 {label_rcd} [{phase}]: {len(lst)} obw. (waga {total}) → {items}")

        self._board_log("\n".join(out))
        self._phase_of_group = phase_of_group  # do rysowania podpisów
        self.draw_board()

    def _is_bath(self, m: Module)->bool:
        s = (m.label or "").lower()
        return ("łazien" in s) or ("lazien" in s)

    def _is_kitchen(self, m: Module)->bool:
        s = (m.label or "").lower()
        return "kuch" in s

    def _pick_free_rcd_for_exclusive(self, rcd_idx:List[int], used:set, m:Module)->Optional[int]:
        free = [r for r in rcd_idx if r not in used]
        if not free: return None
        return min(free, key=lambda r: self._distance(m, self.modules[r]))

    def _assign_phases_to_groups(self, sums:Dict[int,int])->Dict[int,str]:
        # prosto: greedy balans do L1/L2/L3
        phase_loads = {"L1":0,"L2":0,"L3":0}
        out = {}
        for rcd, s in sorted(sums.items(), key=lambda kv: -kv[1]):
            # wybierz fazę o najmniejszym aktualnym obciążeniu
            phase = min(phase_loads.keys(), key=lambda p: phase_loads[p])
            out[rcd] = phase
            phase_loads[phase] += s
        return out

    def _draw_rcd_groups_with_phases(self):
        if not self.rcd_groups: return
        MOD_W = BASE_MOD_W * self.scale
        color_idx = 0
        for rcd_idx, mcb_list in self.rcd_groups.items():
            if not mcb_list: continue
            col = GROUP_COLORS[color_idx % len(GROUP_COLORS)]; color_idx += 1
            rcd = self.modules[rcd_idx]
            rx1,ry1,rx2,ry2 = self._m_rect(rcd)
            rcd_x = (rx1+rx2)//2; rcd_y = ry1 - 6*self.scale
            xs=xe=yy=None
            for i in sorted(mcb_list, key=lambda i: (self.modules[i].row, self.modules[i].col)):
                x1,y1,x2,_ = self._m_rect(self.modules[i])
                yb = y1 - 8*self.scale
                xs = x1 if xs is None else min(xs,x1)
                xe = x2 if xe is None else max(xe,x2)
                yy = yb if yy is None else min(yy,yb)
            if xs is not None:
                self.board_canvas.create_line(xs, yy, xe, yy, fill=col, width=max(2,int(2*self.scale)))
                self.board_canvas.create_line(rcd_x, rcd_y, rcd_x, yy-6*self.scale, fill=col, width=max(1,int(1*self.scale)))
                # podpis fazy
                phase = getattr(self, "_phase_of_group", {}).get(rcd_idx, "L1")
                self.board_canvas.create_text((xs+xe)//2, yy-10*self.scale, text=f"Grupa RCD • {phase}",
                                              fill=col, font=("Segoe UI", int(8*self.scale), "bold"))

    # ---------- SYNC / OBWODY ----------
    def _build_circuit_list(self):
        self.lb_circuits.delete(0,"end")
        for c in self.circuits:
            mark = "✓" if c.assigned else "–"
            self.lb_circuits.insert("end", f"{c.cid} | {c.breaker} | {c.name}   [{mark}]")

    def add_circuit(self):
        next_idx = len(self.circuits)+1
        cid = f"O{next_idx}"
        name = simpledialog.askstring("Nowy obwód", "Nazwa (np. O4 Oświetlenie Piętro):", initialvalue=f"{cid} Nowy")
        if not name: return
        brk = simpledialog.askstring("Wyłącznik", "Typ (B10/B16/C20):", initialvalue="B16") or "B16"
        self.circuits.append(Circuit(cid, name, brk, False))
        self._build_circuit_list(); self._mark_dirty()

    def del_circuit(self):
        sel = self.lb_circuits.curselection()
        if not sel: return
        line = self.lb_circuits.get(sel[0])
        cid = line.split("|")[0].strip()
        # odpinamy moduły z tym obwodem
        for m in self.modules:
            if m.circuit_id == cid: m.circuit_id = None
        self.circuits = [c for c in self.circuits if c.cid != cid]
        self._recalc_circuit_assignments()
        self._build_circuit_list(); self.draw_board(); self._mark_dirty()

    def autopin_free_circuits(self):
        free = [c for c in self.circuits if not c.assigned]
        if not free:
            self._log_sync("Brak wolnych obwodów do przypięcia."); return
        placed = []
        for c in free:
            pos = self._find_first_free_slot(width=1)
            if not pos: break
            row,col = pos
            label = f"{c.breaker} {c.cid} {c.name}"
            self.modules.append(Module(row,col,1,c.breaker,label,c.cid))
            c.assigned = True; placed.append(c.cid)
        if placed:
            self._log_sync(f"Przypięto MCB dla: {', '.join(placed)}.")
            self._mark_dirty()
        else:
            self._log_sync("Brak wolnego miejsca na panelu (zwiększ układ lub usuń coś).")
        self.draw_board(); self._build_circuit_list(); self._report_board()

    def _find_first_free_slot(self, width:int)->Optional[Tuple[int,int]]:
        for r in range(self.rows):
            c = 0
            while c <= self.cols - width:
                if not self._overlaps(r,c,width): return (r,c)
                c += 1
        return None

    def _mark_circuit_assigned(self, cid:str):
        for c in self.circuits:
            if c.cid == cid: c.assigned = True; return

    def _recalc_circuit_assignments(self):
        for c in self.circuits: c.assigned = False
        for m in self.modules:
            if m.circuit_id: self._mark_circuit_assigned(m.circuit_id)

    # ---------- KOLIZJE / TOOLTIP ----------
    def _overlaps(self, row:int, col:int, width:int, ignore_idx:Optional[int]=None)->bool:
        for i,m in enumerate(self.modules):
            if ignore_idx is not None and i==ignore_idx: continue
            if m.row != row: continue
            if not (col+width <= m.col or m.col+m.width <= col): return True
        return False

    def _find_module_starting_at(self, row:int, col:int)->Optional[int]:
        for i,m in enumerate(self.modules):
            if m.row==row and m.col==col: return i
        return None

    def _on_motion_board(self, e):
        idx = self._module_index_at(e.x, e.y)
        if idx is None: self._clear_tooltip(); return
        self._show_tooltip_mod(idx, e.x, e.y)

    def _module_index_at(self, x:int, y:int)->Optional[int]:
        for i,m in enumerate(self.modules):
            x1,y1,x2,y2 = self._m_rect(m)
            if x1<=x<=x2 and y1<=y<=y2: return i
        return None

    def _show_tooltip_mod(self, idx:int, x:int, y:int):
        m = self.modules[idx]
        txt = f"{m.code or 'PUSTE'} | {m.label or '—'}\nRząd: {m.row+1}, Kol: {m.col+1}..{m.col+m.width}\nObwód: {m.circuit_id or '—'}"
        self._clear_tooltip()
        self._tip_box = self.board_canvas.create_rectangle(x+14, y+14, x+270, y+72, fill="#111827", outline="#111827")
        self._tip_txt = self.board_canvas.create_text(x+22, y+20, anchor="nw", text=txt, fill="#e5e7eb", font=("Segoe UI", 9))

    def _clear_tooltip(self):
        if hasattr(self, "_tip_box") and self._tip_box:
            self.board_canvas.delete(self._tip_box); self._tip_box=None
        if hasattr(self, "_tip_txt") and self._tip_txt:
            self.board_canvas.delete(self._tip_txt); self._tip_txt=None

    # ---------- EKSPORT ----------
    def export_csv(self):
        if not self.modules:
            messagebox.showinfo("CSV","Brak aparatów do eksportu."); return
        path = filedialog.asksaveasfilename(title="Zapisz BOM CSV", defaultextension=".csv",
                                            filetypes=[("CSV","*.csv")], initialfile="BOM_rozdzielnica.csv")
        if not path: return
        try:
            import csv
            with open(path,"w",newline="",encoding="utf-8") as f:
                w=csv.writer(f, delimiter=";")
                w.writerow(["Rząd","Kol_start","Szer","Typ","Etykieta","Obwód"])
                for m in self.modules:
                    w.writerow([m.row+1, m.col+1, m.width, m.code, m.label, m.circuit_id or ""])
            messagebox.showinfo("CSV", f"Zapisano: {path}")
        except Exception as e:
            messagebox.showerror("CSV", f"Błąd zapisu: {e}")

    def save_png(self):
        path = filedialog.asksaveasfilename(title="Zapisz PNG frontu", defaultextension=".png",
                                            filetypes=[("PNG","*.png")], initialfile="front_rozdzielnica.png")
        if not path: return
        try:
            from PIL import ImageGrab
            x = self.winfo_rootx() + self.board_canvas.winfo_x()
            y = self.winfo_rooty() + self.board_canvas.winfo_y()
            x1 = x + self.board_canvas.winfo_width()
            y1 = y + self.board_canvas.winfo_height()
            img = ImageGrab.grab().crop((x, y, x1, y1))
            img.save(path)
            messagebox.showinfo("PNG", f"Zapisano: {path}")
        except Exception as e:
            messagebox.showerror("PNG", f"Nie udało się zapisać PNG: {e}\nZainstaluj Pillow: pip install pillow")

    # ---------- UKŁAD / SKALA ----------
    def _apply_layout(self):
        choice = self.cmb_layout.get()
        if choice=="2×12": self.rows,self.cols=2,12
        elif choice=="3×18": self.rows,self.cols=3,18
        elif choice=="1×12": self.rows,self.cols=1,12
        else:
            r = simpledialog.askinteger("Układ","Liczba rzędów:",minvalue=1,maxvalue=8,initialvalue=self.rows)
            c = simpledialog.askinteger("Układ","Liczba kolumn:",minvalue=4,maxvalue=36,initialvalue=self.cols)
            if not r or not c: return
            self.rows,self.cols=r,c
        if self.modules and not messagebox.askyesno("Układ","Zmiana układu usunie bieżący front. Kontynuować?"): return
        self.modules.clear(); self.rcd_groups.clear(); self._mark_dirty()
        self.draw_board(); self._report_board()

    def _on_resize(self, event):
        if event.widget != self: return
        cw = max(600, self.board_canvas.winfo_width()); ch = max(400, self.board_canvas.winfo_height())
        req_w = self.cols*BASE_MOD_W + 2*BASE_PAD + 80
        req_h = self.rows*BASE_MOD_H + (self.rows-1)*BASE_ROW_GAP + 2*BASE_PAD + 40
        s_w = cw / max(req_w,1); s_h = ch / max(req_h,1)
        new_scale = max(0.6, min(1.6, min(s_w, s_h)))
        if abs(new_scale - self.scale) > 0.05:
            self.scale = new_scale; self.draw_board()

    def _clear_board(self):
        if self.modules and not messagebox.askyesno("Wyczyść","Usunąć wszystkie aparaty?"): return
        self.modules.clear(); self.rcd_groups.clear(); self._mark_dirty()
        self.draw_board(); self._report_board()

    # ---------- RAPORTY ----------
    def _report_board(self):
        n_rcd = sum(1 for m in self.modules if m.code=="RCD")
        n_mcb = sum(1 for m in self.modules if is_mcb(m.code))
        msg = f"RCD: {n_rcd} | MCB: {n_mcb}\nKliknij „Analizuj i sugeruj” (reguły: Łazienka osobny RCD, Kuchnia ≤ {self.kitchen_limit}/RCD).\n"
        self._board_log(msg)

    def _board_log(self, text:str):
        self.out_board.delete("1.0","end"); self.out_board.insert("end", text)

    def _log_sync(self, text:str):
        if hasattr(self, "out_sync"):
            self.out_sync.insert("end", text+"\n"); self.out_sync.see("end")

    # ---------- JSON PERSIST ----------
    def _project_state(self)->dict:
        return {
            "version": "1.9.0",
            "layout": {"rows": self.rows, "cols": self.cols},
            "modules": [asdict(m) for m in self.modules],
            "circuits": [asdict(c) for c in self.circuits],
            "rcd_limit": self.rcd_limit,
            "kitchen_limit": self.kitchen_limit
        }

    def _apply_state(self, data:dict):
        self.rows = int(data.get("layout",{}).get("rows",2))
        self.cols = int(data.get("layout",{}).get("cols",12))
        self.modules = [Module(**m) for m in data.get("modules",[])]
        self.circuits = [Circuit(**c) for c in data.get("circuits",[])]
        self.rcd_limit = int(data.get("rcd_limit", MAX_MCB_PER_RCD_DEFAULT))
        self.kitchen_limit = int(data.get("kitchen_limit", KITCHEN_PER_RCD_LIMIT_DEFAULT))
        self.rcd_groups.clear()
        self._recalc_circuit_assignments()

    def _save_project(self):
        try:
            with open(self.project_path, "w", encoding="utf-8") as f:
                json.dump(self._project_state(), f, ensure_ascii=False, indent=2)
            self.dirty = False
            self._log_sync(f"Zapisano projekt: {self.project_path}")
        except Exception as e:
            messagebox.showerror("Zapis", f"Nie udało się zapisać projektu: {e}")

    def _load_project(self)->bool:
        if not os.path.exists(self.project_path): return False
        try:
            with open(self.project_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_state(data)
            self.dirty = False
            return True
        except Exception as e:
            self._log_sync(f"Nie udało się wczytać projektu: {e}")
            return False

    def _new_project(self):
        if self.dirty and not messagebox.askyesno("Niezapisane zmiany","Zapisać projekt przed utworzeniem nowego?"):
            pass
        elif self.dirty:
            self._save_project()
        self.rows,self.cols = 2,12
        self.modules.clear()
        self.circuits = [
            Circuit("O1","O1 Gniazda", "B16"),
            Circuit("O2","O2 Oświetlenie", "B10"),
            Circuit("O3","O3 Rolety", "B16"),
        ]
        self.rcd_groups.clear()
        self._build_circuit_list()
        self.draw_board(); self._report_board()
        self._mark_dirty()

    def _open_project_dialog(self):
        path = filedialog.askopenfilename(title="Otwórz projekt JSON", filetypes=[("JSON","*.json")])
        if not path: return
        try:
            with open(path,"r",encoding="utf-8") as f: data = json.load(f)
            self._apply_state(data)
            self.project_path = path
            self.dirty = False
            self._build_circuit_list(); self.draw_board(); self._report_board()
            self._log_sync(f"Wczytano: {path}")
        except Exception as e:
            messagebox.showerror("Otwórz", f"Nie udało się wczytać pliku: {e}")

    def _save_as_dialog(self):
        path = filedialog.asksaveasfilename(title="Zapisz projekt jako", defaultextension=".json", filetypes=[("JSON","*.json")], initialfile="project.json")
        if not path: return
        self.project_path = path
        self._save_project()

    def _on_exit(self):
        if self.dirty:
            # autosave
            try:
                self._save_project()
            except Exception:
                pass
        self.destroy()

    def _mark_dirty(self):
        self.dirty = True

    # ---------- POMOCNICZE ----------
    def _refresh_all(self):
        self.draw_board()
        self._build_circuit_list()
        self._report_board()

    def _click_board(self, event):
        r,c = self._rc_from_xy(event.x, event.y)
        if r is None or c is None: return
        self._cell_clicked(r,c)

    def _rc_from_xy(self, x:int, y:int)->Tuple[Optional[int],Optional[int]]:
        MOD_W = BASE_MOD_W * self.scale; MOD_H = BASE_MOD_H * self.scale
        ROW_GAP = BASE_ROW_GAP * self.scale; PAD = BASE_PAD * self.scale
        for r in range(self.rows):
            y1 = PAD + r*(MOD_H + ROW_GAP); y2 = y1 + MOD_H
            if y1 <= y <= y2:
                c = int((x - PAD) // MOD_W)
                if 0 <= c < self.cols: return r,c
        return None,None

    def _distance(self, a: Module, b: Module) -> int:
        ax1,ay1,ax2,ay2 = self._m_rect(a); bx1,by1,bx2,by2 = self._m_rect(b)
        ax=(ax1+ax2)//2; ay=(ay1+ay2)//2; bx=(bx1+bx2)//2; by=(by1+by2)//2
        return int(abs(ax-bx)+abs(ay-by))

    def _nearest_rcd_distance(self, m_idx:int, rcd_idx:List[int])->int:
        m = self.modules[m_idx]
        return min((self._distance(m, self.modules[r]) for r in rcd_idx), default=0)

    def _estimate_weight(self, m: Module)->int:
        label = (m.label or "").lower()
        for key, weight in WEIGHTS_DEFAULT.items():
            if key in label:
                return weight
        return WEIGHT_FALLBACK

if __name__ == "__main__":
    App().mainloop()
# ⏹ KONIEC KODU
