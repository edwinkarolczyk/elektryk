# Domowy Elektryk v1.8.0 — integracja: Plan/Mapa + Rozdzielnica + Synchronizacja
# • Rozdzielnica: klik/siatka, proporcje 1:4, szerokości (poles), kolizje, tooltipy, eksport PNG/CSV
# • Wspólne szyny N i PE w rozdzielnicy (mostki z MCB)
# • Lista obwodów + auto-przypinanie „wolnych” do pierwszych wolnych pól MCB
# • Sugestie grup RCD (belki) i limit MCB/RCD
# • Dopasowanie do okna (skalowanie canvasa)
# Autor: ChatGPT Codex — 2025-10-08

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import re

# ------ USTAWIENIA GRAFIKI (bazowe; będą skalowane do okna) ------
BASE_MOD_W = 48          # szerokość 1 modułu DIN (px)
BASE_MOD_H = BASE_MOD_W*4  # wysokość ~4× szerokość (jak „esy”)
BASE_ROW_GAP = 12
BASE_PAD = 24

GROUP_COLORS = ["#2563eb","#16a34a","#f59e0b","#ef4444","#9333ea","#0ea5e9","#84cc16","#fb7185"]

# ------ TYPY APARATÓW ------
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
# rozpoznawanie MCB po kodzie:
def is_mcb(code:str)->bool:
    return bool(code) and (code.startswith("B") or code.startswith("C"))

# Heurystyka wag dla grup RCD
WEIGHTS_DEFAULT = {"gniazd":2, "agd":3, "łazien":3, "lazien":3, "kuch":3, "oświet":1, "oswiet":1, "garaż":2, "garaz":2}
WEIGHT_FALLBACK = 2
MAX_MCB_PER_RCD_DEFAULT = 6

# ------ MODELE ------
@dataclass
class Module:
    row: int
    col: int
    width: int     # w „modułach” DIN (poles)
    code: str      # FR/RCD/B16/...
    label: str     # np. „B16 O1 Gniazda x6”
    circuit_id: Optional[str] = None  # skojarzenie z obwodem (opcjonalnie)

@dataclass
class Circuit:
    cid: str       # O1/O2/...
    name: str      # np. „O1 Gniazda Salon”
    breaker: str   # np. B16/B10/C20
    assigned: bool = False  # czy ma MCB w rozdzielnicy

# ------ APP ------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Domowy Elektryk v1.8.0 — Plan • Rozdzielnica • Synchronizacja")
        self.geometry("1400x820")
        self.minsize(1200, 700)

        # baza układu
        self.rows, self.cols = 2, 12
        self.modules: List[Module] = []
        self.circuits: List[Circuit] = [
            Circuit("O1","O1 Gniazda", "B16"),
            Circuit("O2","O2 Oświetlenie", "B10"),
            Circuit("O3","O3 Rolety", "B16")
        ]
        # grupy RCD (index modułu RCD -> [indexy MCB])
        self.rcd_groups: Dict[int, List[int]] = {}
        self.rcd_limit = MAX_MCB_PER_RCD_DEFAULT

        # skalowanie canvasa
        self.scale = 1.0
        self.bind("<Configure>", self._on_resize)

        self._build_ui()
        self._refresh_all()

    # ---------- UI ----------
    def _build_ui(self):
        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True)

        # --- Zakładka Plan/Mapa (mini) ---
        self.tab_plan = ttk.Frame(self.nb)
        self.nb.add(self.tab_plan, text="Plan / Mapa")
        self._build_plan_tab()

        # --- Rozdzielnica ---
        self.tab_board = ttk.Frame(self.nb)
        self.nb.add(self.tab_board, text="Rozdzielnica")
        self._build_board_tab()

        # --- Synchronizacja ---
        self.tab_sync = ttk.Frame(self.nb)
        self.nb.add(self.tab_sync, text="Synchronizacja")
        self._build_sync_tab()

    # ---------- PLAN ----------
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
        # rysuj przykładowo białe przewody i kropki obwodów (czysto wizualnie)
        self.plan_canvas.create_line(80,300,380,300, width=2, fill="#ffffff")
        self.plan_canvas.create_line(480,320,620,160, width=2, fill="#ffffff", dash=(4,4))
        for (x,y,label,color) in [(80,300,"RG","#111"),(380,300,"G-01","#111"),(620,160,"L-01","#111"),(480,320,"W-01","#111")]:
            r=18
            self.plan_canvas.create_oval(x-r,y-r,x+r,y+r, fill="#303134", outline="")
            self.plan_canvas.create_text(x,y,text=label, fill="#fff")
            # „kropka” obwodu (symbolicznie)
            self.plan_canvas.create_oval(x+r-8, y-r+2, x+r-2, y-r+8, fill="#2b6cb0", outline="")

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

        mid = ttk.Frame(self.tab_board); mid.pack(fill="both", expand=True, padx=10, pady=(0,10))
        # kontener z przewijaniem i autoskalą
        self.board_canvas = tk.Canvas(mid, bg="#f2f3f5", highlightthickness=1, highlightbackground="#9aa0a6")
        self.board_canvas.pack(side="left", fill="both", expand=True)
        self.board_canvas.bind("<Button-1>", self._click_board)
        self.board_canvas.bind("<Motion>", self._on_motion_board)
        self.board_canvas.bind("<Leave>", lambda e: self._clear_tooltip())

        right = ttk.Frame(mid, width=300); right.pack(side="left", fill="y", padx=(10,0))
        ttk.Label(right, text="Analiza / Podpowiedzi RCD", font=("Segoe UI",10,"bold")).pack(anchor="w")
        fr = ttk.Frame(right); fr.pack(fill="x", pady=6)
        ttk.Label(fr, text="Limit MCB/RCD:").pack(side="left")
        self.spn_limit = tk.Spinbox(fr, from_=2, to=16, width=5)
        self.spn_limit.delete(0,"end"); self.spn_limit.insert(0, str(self.rcd_limit))
        self.spn_limit.pack(side="left", padx=(6,6))
        ttk.Button(fr, text="Analizuj i sugeruj", command=self.analyze_grouping).pack(side="left")

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
        ttk.Button(ops, text="🧠 Analizuj RCD (z rozdz.)", command=self.analyze_grouping).pack(fill="x", pady=(6,0))

        self.out_sync = tk.Text(mid, height=28, wrap="word")
        self.out_sync.pack(fill="both", expand=True)
        self._sync_log("Wskazówka: Dodawaj obwody i użyj „Auto-przypnij wolne obwody”, aby wstawić brakujące MCB w rozdzielnicy.")

    # ---------- RYSOWANIE ROZDZIELNICY ----------
    def draw_board(self):
        c = self.board_canvas
        c.delete("all")

        # dynamiczne wymiary wg skali:
        MOD_W = BASE_MOD_W * self.scale
        MOD_H = BASE_MOD_H * self.scale
        ROW_GAP = BASE_ROW_GAP * self.scale
        PAD = BASE_PAD * self.scale

        W = self.cols*MOD_W + 2*PAD
        H = self.rows*MOD_H + (self.rows-1)*ROW_GAP + 2*PAD
        c.config(scrollregion=(0,0,W,H))

        # Rama panelu
        c.create_rectangle(PAD-12*self.scale, PAD-12*self.scale,
                           PAD + self.cols*MOD_W + 12*self.scale,
                           PAD + self.rows*MOD_H + (self.rows-1)*ROW_GAP + 12*self.scale,
                           outline="#6b7280", width=max(1,self.scale), fill="#e5e7eb")

        # Szyny DIN i siatka
        for r in range(self.rows):
            y_top = PAD + r*(MOD_H + ROW_GAP)
            c.create_rectangle(PAD, y_top + 10*self.scale, PAD + self.cols*MOD_W, y_top + 14*self.scale,
                               fill="#cbd5e1", outline="")
            for cc in range(self.cols):
                x1 = PAD + cc*MOD_W; y1 = y_top; x2 = x1 + MOD_W; y2 = y1 + MOD_H
                tag = f"cell-{r}-{cc}"
                c.create_rectangle(x1, y1, x2, y2, outline="#111", fill="#ffffff", tags=tag)
                c.tag_bind(tag, "<Button-1>", lambda e, rr=r, cc=cc: self._cell_clicked(rr, cc))
                if r == self.rows-1:
                    c.create_text(x1 + MOD_W/2, y2 + 12*self.scale, text=str(cc+1), fill="#374151", font=("Segoe UI", int(8*self.scale)))

        # Wspólne szyny N/PE po prawej
        right_x = PAD + self.cols*MOD_W + 18*self.scale
        top_y = PAD
        # N (niebieska listwa)
        c.create_rectangle(right_x, top_y, right_x+12*self.scale, top_y + self.rows*MOD_H + (self.rows-1)*ROW_GAP,
                           fill="#3b82f6", outline="#1d4ed8")
        c.create_text(right_x+6*self.scale, top_y-10*self.scale, text="N", fill="#1d4ed8", font=("Segoe UI", int(10*self.scale)))
        # PE (żółto-zielona)
        right_x2 = right_x + 22*self.scale
        c.create_rectangle(right_x2, top_y, right_x2+12*self.scale, top_y + self.rows*MOD_H + (self.rows-1)*ROW_GAP,
                           fill="#84cc16", outline="#166534")
        c.create_text(right_x2+6*self.scale, top_y-10*self.scale, text="PE", fill="#166534", font=("Segoe UI", int(10*self.scale)))

        # Moduły
        for idx, m in enumerate(self.modules):
            x1, y1, x2, y2 = self._m_rect(m)  # w skali
            c.create_rectangle(x1+1, y1+1, x2-1, y2-1, fill="#ffffff", outline="#111")
            c.create_rectangle(x1+1, y1+1, x2-1, y1+12*self.scale, fill="#d1d5db", outline="#d1d5db")
            c.create_text((x1+x2)//2, (y1+y2)//2, text=(m.label or m.code or " "),
                          font=("Segoe UI", int(10*self.scale)), fill="#111")
            tag = f"mod-{idx}"
            c.create_rectangle(x1+1, y1+1, x2-1, y2-1, outline="", fill="", tags=tag)
            c.tag_bind(tag, "<Button-1>", lambda e, i=idx: self._edit_module(i))
            c.tag_bind(tag, "<Motion>", lambda e, i=idx: self._show_tooltip_mod(i, e.x, e.y))

            # Mostki do N/PE dla MCB:
            if is_mcb(m.code):
                midx = (x1+x2)/2
                # małe odcinki „wyjść” z dołu modułu
                c.create_line(midx, y2, midx, y2+10*self.scale, fill="#111", width=max(1,int(1*self.scale)))
                # do N
                c.create_line(midx, y2+10*self.scale, right_x, y2+10*self.scale, fill="#3b82f6")
                # do PE (odrobina niżej)
                c.create_line(midx, y2+16*self.scale, right_x2, y2+16*self.scale, fill="#84cc16")

        # Belki grup RCD (jeśli są)
        self._draw_rcd_groups()

    def _m_rect(self, m: Module) -> Tuple[float,float,float,float]:
        MOD_W = BASE_MOD_W * self.scale
        MOD_H = BASE_MOD_H * self.scale
        ROW_GAP = BASE_ROW_GAP * self.scale
        PAD = BASE_PAD * self.scale
        x1 = PAD + m.col * MOD_W
        y1 = PAD + m.row * (MOD_H + ROW_GAP)
        x2 = x1 + m.width * MOD_W
        y2 = y1 + MOD_H
        return x1,y1,x2,y2

    def _draw_rcd_groups(self):
        if not self.rcd_groups: return
        MOD_W = BASE_MOD_W * self.scale
        PAD = BASE_PAD * self.scale
        color_idx = 0
        for rcd_idx, mcb_list in self.rcd_groups.items():
            if not mcb_list: continue
            col = GROUP_COLORS[color_idx % len(GROUP_COLORS)]; color_idx += 1
            rcd = self.modules[rcd_idx]
            rx1, ry1, rx2, ry2 = self._m_rect(rcd)
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
                self.board_canvas.create_text((xs+xe)//2, yy-10*self.scale, text="Grupa RCD", fill=col,
                                              font=("Segoe UI", int(8*self.scale), "bold"))

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

        def prefill(*_):
            _, code, poles = MODULE_TYPES[cmb.current()]
            if not ent_label.get(): ent_label.insert(0, code)
            spn.delete(0,"end"); spn.insert(0, str(poles))
        prefill(); cmb.bind("<<ComboboxSelected>>", prefill)

        # powiązanie z obwodem (opcjonalnie)
        ttk.Label(frm, text="Przypisz obwód (opc.):").grid(row=3,column=0,sticky="w")
        cids = ["—"] + [c.cid for c in self.circuits]
        cmb_cid = ttk.Combobox(frm, state="readonly", values=cids, width=10); cmb_cid.current(0)
        cmb_cid.grid(row=3,column=1,sticky="w",pady=4)

        def ok():
            name, code, pdef = MODULE_TYPES[cmb.current()]
            label = ent_label.get().strip() or code
            try: width = int(spn.get())
            except: width = pdef
            width = max(1, min(width, self.cols))
            if col + width > self.cols: width = self.cols - col
            if self._overlaps(row,col,width):
                messagebox.showerror("Kolizja","Te pola są już zajęte."); return
            circuit_id = None
            if cmb_cid.get() != "—": circuit_id = cmb_cid.get()
            self.modules.append(Module(row,col,width,code,label,circuit_id))
            if circuit_id:
                self._mark_circuit_assigned(circuit_id)
            self.rcd_groups.clear()
            self.draw_board(); self._report_board(); top.destroy()

        btns = ttk.Frame(frm); btns.grid(row=4,column=0,columnspan=2,pady=(10,0))
        ttk.Button(btns, text="OK", command=ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Anuluj", command=top.destroy).pack(side="left", padx=4)

    def _edit_module(self, idx:int):
        m = self.modules[idx]
        top = tk.Toplevel(self); top.title(f"Edycja: {m.label or m.code}"); top.grab_set()
        frm = ttk.Frame(top); frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Typ aparatu:").grid(row=0,column=0,sticky="w")
        cmb = ttk.Combobox(frm, state="readonly", width=28, values=[n for n,_,_ in MODULE_TYPES])
        cur = 0
        for i,(_,code,_) in enumerate(MODULE_TYPES):
            if code == m.code: cur = i; break
        cmb.current(cur); cmb.grid(row=0,column=1,sticky="ew",pady=4)

        ttk.Label(frm, text="Etykieta:").grid(row=1,column=0,sticky="w")
        ent_label = ttk.Entry(frm, width=28); ent_label.insert(0, m.label); ent_label.grid(row=1,column=1,sticky="ew",pady=4)

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
            label = ent_label.get().strip() or code
            try: width = int(spn.get())
            except: width = m.width
            width = max(1, min(width, self.cols))
            if m.col + width > self.cols: width = self.cols - m.col
            if self._overlaps(m.row,m.col,width,ignore_idx=idx):
                messagebox.showerror("Kolizja","Zmiana szerokości nachodzi na inny moduł."); return
            m.code, m.label, m.width = code, label, width
            # obwód
            new_cid = None if cmb_cid.get()=="—" else cmb_cid.get()
            m.circuit_id = new_cid
            self._recalc_circuit_assignments()
            self.rcd_groups.clear()
            self.draw_board(); self._report_board(); top.destroy()

        def delete():
            if messagebox.askyesno("Usuń", f"Usunąć „{m.label or m.code}”?"):
                del self.modules[idx]
                self._recalc_circuit_assignments()
                self.rcd_groups.clear()
                self.draw_board(); self._report_board(); top.destroy()

        btns = ttk.Frame(frm); btns.grid(row=4,column=0,columnspan=2,pady=(10,0))
        ttk.Button(btns, text="Zapisz", command=save).pack(side="left", padx=4)
        ttk.Button(btns, text="Usuń", command=delete).pack(side="left", padx=4)
        ttk.Button(btns, text="Anuluj", command=top.destroy).pack(side="left", padx=4)

    # ---------- ANALIZA / RCD ----------
    def analyze_grouping(self):
        try: self.rcd_limit = int(self.spn_limit.get())
        except: self.rcd_limit = MAX_MCB_PER_RCD_DEFAULT

        rcd_idx = [i for i,m in enumerate(self.modules) if m.code=="RCD"]
        mcb_idx = [i for i,m in enumerate(self.modules) if is_mcb(m.code)]
        self.rcd_groups.clear()
        info = []

        if not rcd_idx:
            need = max(1, (len(mcb_idx)+self.rcd_limit-1)//self.rcd_limit) if mcb_idx else 1
            info.append(f"⚠️ Brak RCD. Sugerowane: {need} (limit {self.rcd_limit} MCB/RCD).")
            self._board_log("\n".join(info)); self.draw_board(); return

        weights = {i: self._estimate_weight(self.modules[i]) for i in mcb_idx}
        for r in rcd_idx: self.rcd_groups[r] = []
        sums = {r:0 for r in rcd_idx}; counts = {r:0 for r in rcd_idx}

        for i in sorted(mcb_idx, key=lambda k: (-weights[k], self._nearest_rcd_distance(k, rcd_idx))):
            # wybierz RCD z najmniejszą sumą i miejscem
            candidates = sorted(rcd_idx, key=lambda r: (sums[r], self._distance(self.modules[i], self.modules[r])))
            chosen = None
            for r in candidates:
                if counts[r] < self.rcd_limit:
                    chosen = r; break
            if chosen is None:
                chosen = min(rcd_idx, key=lambda r: self._distance(self.modules[i], self.modules[r]))
            self.rcd_groups[chosen].append(i)
            sums[chosen] += weights[i]; counts[chosen] += 1

        for r in rcd_idx:
            lst = self.rcd_groups[r]; total = sum(weights[i] for i in lst)
            label_rcd = self.modules[r].label or "RCD 30mA"
            items = ", ".join(self.modules[i].label or self.modules[i].code for i in lst) or "—"
            info.append(f"🟢 {label_rcd}: {len(lst)} obw. (waga {total}) → {items}")

        self._board_log("\n".join(info))
        self.draw_board()

    def _estimate_weight(self, m: Module) -> int:
        s = (m.label or "").lower()
        m1 = re.search(r"x\s*(\d+)", s)
        if m1:
            n = int(m1.group(1))
            base = WEIGHT_FALLBACK
            for k,v in WEIGHTS_DEFAULT.items():
                if k in s: base = v; break
            return max(1, base*max(1,n))
        for k,v in WEIGHTS_DEFAULT.items():
            if k in s: return v
        return WEIGHT_FALLBACK

    def _distance(self, a: Module, b: Module) -> int:
        ax1,ay1,ax2,ay2 = self._m_rect(a); bx1,by1,bx2,by2 = self._m_rect(b)
        ax=(ax1+ax2)//2; ay=(ay1+ay2)//2; bx=(bx1+bx2)//2; by=(by1+by2)//2
        return int(abs(ax-bx)+abs(ay-by))

    def _nearest_rcd_distance(self, idx:int, rcd_idx:List[int])->int:
        m = self.modules[idx]
        return min(self._distance(m, self.modules[r]) for r in rcd_idx) if rcd_idx else 0

    # ---------- SYNC: OBWODY ----------
    def _refresh_circuit_list(self):
        self.lb_circuits.delete(0,"end")
        for c in self.circuits:
            mark = "✓" if c.assigned else "–"
            self.lb_circuits.insert("end", f"{c.cid} | {c.breaker} | {c.name}   [{mark}]")

    def add_circuit(self):
        next_idx = len(self.circuits)+1
        cid = f"O{next_idx}"
        name = simpledialog.askstring("Nowy obwód", "Nazwa (np. O4 Oświetlenie Piętro):",
                                      initialvalue=f"{cid} Nowy")
        if not name: return
        brk = simpledialog.askstring("Wyłącznik", "Typ (B10/B16/C20):", initialvalue="B16") or "B16"
        self.circuits.append(Circuit(cid, name, brk, False))
        self._refresh_circuit_list()

    def del_circuit(self):
        sel = self.lb_circuits.curselection()
        if not sel: return
        line = self.lb_circuits.get(sel[0])
        cid = line.split("|")[0].strip()
        # odpinamy moduły z tym obwodem
        for m in self.modules:
            if m.circuit_id == cid:
                m.circuit_id = None
        self.circuits = [c for c in self.circuits if c.cid != cid]
        self._recalc_circuit_assignments()
        self._refresh_circuit_list()
        self.draw_board()

    def autopin_free_circuits(self):
        # znajdź wolne
        free = [c for c in self.circuits if not c.assigned]
        if not free:
            self._sync_log("Brak wolnych obwodów do przypięcia."); return
        placed = []
        for c in free:
            pos = self._find_first_free_slot(width=1)
            if not pos: break
            row,col = pos
            label = f"{c.breaker} {c.cid}"
            self.modules.append(Module(row,col,1,c.breaker,label,c.cid))
            c.assigned = True
            placed.append(c.cid)
        if placed:
            self._sync_log(f"Przypięto MCB dla: {', '.join(placed)}.")
        else:
            self._sync_log("Brak wolnego miejsca na panelu (zwiększ układ lub usuń coś).")
        self.draw_board(); self._refresh_circuit_list(); self._report_board()

    def _find_first_free_slot(self, width:int) -> Optional[Tuple[int,int]]:
        for r in range(self.rows):
            c = 0
            while c <= self.cols - width:
                if not self._overlaps(r,c,width):
                    return (r,c)
                c += 1
        return None

    def _mark_circuit_assigned(self, cid:str):
        for c in self.circuits:
            if c.cid == cid:
                c.assigned = True; return

    def _recalc_circuit_assignments(self):
        # reset
        for c in self.circuits: c.assigned = False
        for m in self.modules:
            if m.circuit_id:
                self._mark_circuit_assigned(m.circuit_id)

    # ---------- NARZĘDZIA / KOLIZJE / TOOLTIP ----------
    def _overlaps(self, row:int, col:int, width:int, ignore_idx:Optional[int]=None)->bool:
        for i,m in enumerate(self.modules):
            if ignore_idx is not None and i==ignore_idx: continue
            if m.row != row: continue
            if not (col+width <= m.col or m.col+m.width <= col):
                return True
        return False

    def _find_module_starting_at(self, row:int, col:int)->Optional[int]:
        for i,m in enumerate(self.modules):
            if m.row==row and m.col==col: return i
        return None

    def _on_motion_board(self, e):
        idx = self._module_index_at(e.x, e.y)
        if idx is None:
            self._clear_tooltip(); return
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
        self._tip_txt = self.board_canvas.create_text(x+22, y+20, anchor="nw", text=txt, fill="#e5e7eb",
                                                      font=("Segoe UI", 9))

    def _clear_tooltip(self):
        if hasattr(self, "_tip_box") and self._tip_box:
            self.board_canvas.delete(self._tip_box); self._tip_box=None
        if hasattr(self, "_tip_txt") and self._tip_txt:
            self.board_canvas.delete(self._tip_txt); self._tip_txt=None

    # ---------- EKSPORT / UKŁAD ----------
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
            messagebox.showerror("PNG", f"Błąd zapisu PNG: {e}\nZainstaluj Pillow: pip install pillow")

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
        if self.modules and not messagebox.askyesno("Układ","Zmiana układu usunie bieżący front. Kontynuować?"):
            return
        self.modules.clear(); self.rcd_groups.clear()
        self.draw_board(); self._report_board()

    def _clear_board(self):
        if self.modules and not messagebox.askyesno("Wyczyść","Usunąć wszystkie aparaty?"): return
        self.modules.clear(); self.rcd_groups.clear()
        self.draw_board(); self._report_board()

    # ---------- RAPORTY / LOGI ----------
    def _report_board(self):
        n_rcd = sum(1 for m in self.modules if m.code=="RCD")
        n_mcb = sum(1 for m in self.modules if is_mcb(m.code))
        msg = f"RCD: {n_rcd} | MCB: {n_mcb}\nKliknij „Analizuj i sugeruj”, aby zaproponować grupy pod RCD.\n"
        self._board_log(msg)

    def _board_log(self, text:str):
        self.out_board.delete("1.0","end"); self.out_board.insert("end", text)

    def _sync_log(self, text:str):
        self.out_sync.insert("end", text+"\n"); self.out_sync.see("end")

    def _refresh_all(self):
        self.draw_board()
        self._refresh_circuit_list()
        self._report_board()

    # ---------- Canvas click helper ----------
    def _click_board(self, event):
        r,c = self._rc_from_xy(event.x, event.y)
        if r is None or c is None: return
        self._cell_clicked(r,c)

    def _rc_from_xy(self, x:int, y:int)->Tuple[Optional[int],Optional[int]]:
        MOD_W = BASE_MOD_W * self.scale
        MOD_H = BASE_MOD_H * self.scale
        ROW_GAP = BASE_ROW_GAP * self.scale
        PAD = BASE_PAD * self.scale
        for r in range(self.rows):
            y1 = PAD + r*(MOD_H + ROW_GAP); y2 = y1 + MOD_H
            if y1 <= y <= y2:
                c = int((x - PAD) // MOD_W)
                if 0 <= c < self.cols: return r,c
        return None,None

    # ---------- Skalowanie do okna ----------
    def _on_resize(self, event):
        # dopasuj skalę tak, żeby front mieścił się komfortowo
        if event.widget != self: return
        cw = max(600, self.board_canvas.winfo_width())
        ch = max(400, self.board_canvas.winfo_height())
        # policz oczekiwany rozmiar frontu przy skali 1
        req_w = self.cols*BASE_MOD_W + 2*BASE_PAD + 80  # + margines na N/PE
        req_h = self.rows*BASE_MOD_H + (self.rows-1)*BASE_ROW_GAP + 2*BASE_PAD + 40
        s_w = cw / max(req_w,1); s_h = ch / max(req_h,1)
        new_scale = max(0.6, min(1.6, min(s_w, s_h)))
        if abs(new_scale - self.scale) > 0.05:
            self.scale = new_scale
            self.draw_board()

if __name__ == "__main__":
    App().mainloop()
# ⏹ KONIEC KODU
