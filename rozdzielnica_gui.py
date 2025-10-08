# Domowy Elektryk — Rozdzielnica 2x12 (klik/siatka, poles, proporcje 1:4) v1.6.0
# Funkcje: wybór typu aparatu, szerokości (poles), edycja/usuń, blokada kolizji,
# tooltip, eksport CSV (BOM), zapis PNG (front).
# Autor: ChatGPT Codex — 2025-10-08

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ------------------ Model ------------------

# Lista typów aparatów (etykieta domyślna, domyślne poles)
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

# Proporcje modułu DIN: wysokość ~ 4 × szerokość
MOD_W = 48   # px (szerokość 1 „modułu DIN 18mm”)
MOD_H = MOD_W * 4  # 192px => smukłe i wysokie jak „esy”
ROW_GAP = 12  # szczelina między rzędami
PAD = 24      # margines panelu

@dataclass
class Module:
    row: int
    col: int
    width: int     # ile „modułów” DIN zajmuje w poziomie (poles)
    code: str      # skrót: FR/RCD/B16/...
    label: str     # etykieta wyświetlana (np. „B16 O1”)

    def rect(self) -> Tuple[int, int, int, int]:
        """Obszar modułu w pikselach na canvasie."""
        x1 = PAD + self.col * MOD_W
        y1 = PAD + self.row * (MOD_H + ROW_GAP)
        x2 = x1 + self.width * MOD_W
        y2 = y1 + MOD_H
        return x1, y1, x2, y2

# ------------------ App ------------------

class RozdzielnicaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Domowy Elektryk — Rozdzielnica (klik/siatka)")
        self.geometry("1100x700")
        self.minsize(900, 620)

        # siatka: domyślnie 2×12 (jak chciałeś)
        self.rows, self.cols = 2, 12
        self.modules: List[Module] = []

        # zmienne narzędziowe
        self._hover_id: Optional[int] = None
        self._hover_text: Optional[int] = None
        self._last_mouse = (0, 0)

        self._build_ui()
        self.draw_board()

    # ---------- UI Scaffold ----------
    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=12, pady=8)

        ttk.Label(top, text="Układ:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0,6))
        self.cmb_layout = ttk.Combobox(top, state="readonly", values=["2×12","3×18","1×12","własny…"], width=8)
        self.cmb_layout.current(0)
        self.cmb_layout.pack(side="left")
        ttk.Button(top, text="Ustaw", command=self._apply_layout).pack(side="left", padx=6)

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Button(top, text="Eksport CSV (BOM)", command=self.export_csv).pack(side="left")
        ttk.Button(top, text="Zapisz PNG (front)", command=self.save_png).pack(side="left", padx=6)
        ttk.Button(top, text="Wyczyść", command=self._clear_all).pack(side="left", padx=(6,0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12, pady=(0,6))

        mid = ttk.Frame(self); mid.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas = tk.Canvas(mid, bg="#f2f3f5", highlightthickness=1, highlightbackground="#9aa0a6")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self._click_canvas)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._clear_tooltip())

        # legenda pod spodem
        bottom = ttk.Frame(self); bottom.pack(fill="x", padx=12, pady=(0,12))
        ttk.Label(bottom, text="Podpowiedź: Kliknij puste pole, aby dodać aparat. Kliknij aparat, aby edytować/usuwać.",
                  foreground="#555").pack(side="left")

    # ---------- Rysowanie ----------
    def draw_board(self):
        self.canvas.delete("all")

        W = self.cols * MOD_W + 2 * PAD
        H = self.rows * MOD_H + (self.rows - 1) * ROW_GAP + 2 * PAD
        self.canvas.config(scrollregion=(0, 0, W, H))

        # Rama rozdzielnicy (front)
        self.canvas.create_rectangle(PAD-12, PAD-12, PAD + self.cols*MOD_W + 12,
                                     PAD + self.rows*MOD_H + (self.rows-1)*ROW_GAP + 12,
                                     outline="#6b7280", width=2, fill="#e5e7eb")

        # Rzędy, szyny DIN i siatka klikalna
        for r in range(self.rows):
            y_top = PAD + r * (MOD_H + ROW_GAP)
            # symboliczna listwa DIN (szara belka)
            self.canvas.create_rectangle(PAD, y_top + 10, PAD + self.cols*MOD_W, y_top + 14,
                                         fill="#cbd5e1", outline="")
            # rysuj pola komórek (kontury), numeracja kolumn
            for c in range(self.cols):
                x1 = PAD + c * MOD_W
                y1 = y_top
                x2 = x1 + MOD_W
                y2 = y1 + MOD_H
                tag = f"cell-{r}-{c}"
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="#111", fill="#ffffff", tags=tag)
                self.canvas.tag_bind(tag, "<Button-1>", lambda e, rr=r, cc=c: self._cell_clicked(rr, cc))
                # numeracja kolumn pod ostatnim rzędem
                if r == self.rows - 1:
                    self.canvas.create_text(x1 + MOD_W/2, y2 + 12, text=str(c+1), fill="#374151", font=("Segoe UI", 8))

        # Moduły (białe face + cienka górna maskownica + etykieta)
        for idx, m in enumerate(self.modules):
            x1, y1, x2, y2 = m.rect()
            # tło modułu (białe)
            self.canvas.create_rectangle(x1+1, y1+1, x2-1, y2-1, fill="#ffffff", outline="#111")
            # „maskownica” u góry (ciemniejszy pasek)
            self.canvas.create_rectangle(x1+1, y1+1, x2-1, y1+12, fill="#d1d5db", outline="#d1d5db")
            # etykieta
            self.canvas.create_text((x1+x2)//2, (y1+y2)//2, text=(m.label or m.code or " "),
                                    font=("Segoe UI", 10, "bold"))
            # tag do klikania/tooltipu
            tag = f"mod-{idx}"
            self.canvas.create_rectangle(x1+1, y1+1, x2-1, y2-1, outline="", fill="", tags=tag)
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, i=idx: self._edit_module(i))
            self.canvas.tag_bind(tag, "<Motion>", lambda e, i=idx: self._show_tooltip_mod(i, e.x, e.y))

    # ---------- Logika wstawiania/edycji ----------
    def _cell_clicked(self, row: int, col: int):
        """Klik pustego pola: jeśli w tym miejscu zaczyna się moduł → edycja, w przeciwnym razie wstawianie."""
        hit = self._find_module_starting_at(row, col)
        if hit is not None:
            self._edit_module(hit)
            return
        self._insert_dialog(row, col)

    def _insert_dialog(self, row: int, col: int):
        # wybór typu
        top = tk.Toplevel(self); top.title(f"Dodaj aparat @ r{row+1}/c{col+1}")
        top.grab_set()
        frm = ttk.Frame(top); frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Typ aparatu:").grid(row=0, column=0, sticky="w")
        cmb = ttk.Combobox(frm, state="readonly", width=28,
                           values=[name for name, _, _ in MODULE_TYPES])
        cmb.current(2)  # domyślnie „MCB B10”
        cmb.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Etykieta:").grid(row=1, column=0, sticky="w")
        ent_label = ttk.Entry(frm, width=30)
        ent_label.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Szerokość (poles):").grid(row=2, column=0, sticky="w")
        spn_width = tk.Spinbox(frm, from_=1, to=12, width=5)
        spn_width.grid(row=2, column=1, sticky="w", pady=4)

        def prefill(*_):
            name, code, poles = MODULE_TYPES[cmb.current()]
            if not ent_label.get():
                ent_label.delete(0, "end")
                ent_label.insert(0, code)
            spn_width.delete(0, "end")
            spn_width.insert(0, str(poles))
        prefill()
        cmb.bind("<<ComboboxSelected>>", prefill)

        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=2, pady=(10,0))
        def ok():
            name, code, poles_def = MODULE_TYPES[cmb.current()]
            label = ent_label.get().strip()
            try:
                width = int(spn_width.get())
            except:
                width = poles_def
            if width < 1: width = 1
            if width > self.cols: width = self.cols

            # dopasuj do końca rzędu
            if col + width > self.cols:
                width = self.cols - col

            # kolizje?
            if self._overlaps(row, col, width):
                messagebox.showerror("Kolizja", "Te pola są już zajęte przez inny moduł.")
                return

            self.modules.append(Module(row=row, col=col, width=width, code=code, label=label or code))
            self.draw_board()
            top.destroy()

        ttk.Button(btns, text="OK", command=ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Anuluj", command=top.destroy).pack(side="left", padx=4)

    def _edit_module(self, idx: int):
        """Edycja istniejącego modułu (typ/etykieta/szerokość) + usuń."""
        m = self.modules[idx]
        top = tk.Toplevel(self); top.title(f"Edycja: {m.label or m.code} @ r{m.row+1}/c{m.col+1}")
        top.grab_set()
        frm = ttk.Frame(top); frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Typ aparatu:").grid(row=0, column=0, sticky="w")
        cmb = ttk.Combobox(frm, state="readonly", width=28,
                           values=[name for name, _, _ in MODULE_TYPES])
        # ustal bieżący index
        cur = 0
        for i, (_, code, _) in enumerate(MODULE_TYPES):
            if code == m.code:
                cur = i; break
        cmb.current(cur)
        cmb.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Etykieta:").grid(row=1, column=0, sticky="w")
        ent_label = ttk.Entry(frm, width=30)
        ent_label.insert(0, m.label)
        ent_label.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Szerokość (poles):").grid(row=2, column=0, sticky="w")
        spn_width = tk.Spinbox(frm, from_=1, to=12, width=5)
        spn_width.delete(0, "end"); spn_width.insert(0, str(m.width))
        spn_width.grid(row=2, column=1, sticky="w", pady=4)

        def apply_changes():
            name, code, poles_def = MODULE_TYPES[cmb.current()]
            label = ent_label.get().strip()
            try:
                width = int(spn_width.get())
            except:
                width = m.width
            if width < 1: width = 1
            if width > self.cols: width = self.cols
            # dopasuj do końca rzędu
            if m.col + width > self.cols:
                width = self.cols - m.col
            # sprawdź kolizje z wyjątkiem samego siebie
            if self._overlaps(m.row, m.col, width, ignore_idx=idx):
                messagebox.showerror("Kolizja", "Zmiana szerokości nachodzi na inny moduł.")
                return
            m.code = code
            m.label = label or code
            m.width = width
            self.draw_board()
            top.destroy()

        def delete_mod():
            if messagebox.askyesno("Usuń", f"Czy usunąć moduł „{m.label or m.code}”?"):
                del self.modules[idx]
                self.draw_board()
                top.destroy()

        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=2, pady=(10,0))
        ttk.Button(btns, text="Zapisz", command=apply_changes).pack(side="left", padx=4)
        ttk.Button(btns, text="Usuń", command=delete_mod).pack(side="left", padx=4)
        ttk.Button(btns, text="Anuluj", command=top.destroy).pack(side="left", padx=4)

    # ---------- Narzędzia/kolizje ----------
    def _overlaps(self, row: int, col: int, width: int, ignore_idx: Optional[int]=None) -> bool:
        """Czy [row,col..col+width-1] nachodzi na istniejący moduł?"""
        for i, m in enumerate(self.modules):
            if ignore_idx is not None and i == ignore_idx:
                continue
            if m.row != row:
                continue
            # przedziały: [col, col+width-1] vs [m.col, m.col+m.width-1]
            if not (col + width <= m.col or m.col + m.width <= col):
                return True
        return False

    def _find_module_starting_at(self, row: int, col: int) -> Optional[int]:
        for i, m in enumerate(self.modules):
            if m.row == row and m.col == col:
                return i
        return None

    # ---------- Tooltip ----------
    def _on_motion(self, e):
        self._last_mouse = (e.x, e.y)
        # sprawdź, czy nad modułem
        idx = self._module_index_at(e.x, e.y)
        if idx is None:
            self._clear_tooltip()
            return
        self._show_tooltip_mod(idx, e.x, e.y)

    def _module_index_at(self, x: int, y: int) -> Optional[int]:
        for i, m in enumerate(self.modules):
            x1, y1, x2, y2 = m.rect()
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return None

    def _show_tooltip_mod(self, idx: int, x: int, y: int):
        m = self.modules[idx]
        txt = f"{m.code or 'PUSTE'} | {m.label or '—'}\nRząd: {m.row+1}, Kol: {m.col+1}..{m.col+m.width}"
        self._clear_tooltip()

        pad = 8
        base_x = x + 16
        base_y = y + 16
        self._hover_text = self.canvas.create_text(base_x, base_y, anchor="nw", text=txt,
                                                   fill="#e5e7eb", font=("Segoe UI", 9))

        bbox = self.canvas.bbox(self._hover_text)
        if not bbox:
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        shift_x = 0
        shift_y = 0

        if bbox[2] + pad > canvas_w:
            shift_x = canvas_w - (bbox[2] + pad)
        if bbox[3] + pad > canvas_h:
            shift_y = canvas_h - (bbox[3] + pad)
        if bbox[0] - pad < 0:
            shift_x = max(shift_x, -(bbox[0] - pad))
        if bbox[1] - pad < 0:
            shift_y = max(shift_y, -(bbox[1] - pad))

        if shift_x or shift_y:
            self.canvas.move(self._hover_text, shift_x, shift_y)
            bbox = self.canvas.bbox(self._hover_text)

        self._hover_id = self.canvas.create_rectangle(bbox[0] - pad, bbox[1] - pad,
                                                      bbox[2] + pad, bbox[3] + pad,
                                                      fill="#111827", outline="#111827")
        self.canvas.tag_lower(self._hover_id, self._hover_text)

    def _clear_tooltip(self):
        if self._hover_id:
            self.canvas.delete(self._hover_id); self._hover_id = None
        if self._hover_text:
            self.canvas.delete(self._hover_text); self._hover_text = None

    # ---------- Eksport ----------
    def export_csv(self):
        if not self.modules:
            messagebox.showinfo("CSV", "Brak aparatów do eksportu."); return
        path = filedialog.asksaveasfilename(title="Zapisz BOM CSV", defaultextension=".csv",
                                            filetypes=[("CSV","*.csv")], initialfile="BOM_rozdzielnica.csv")
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Rząd","Kol_start","Szer(z modów)","Typ","Etykieta"])
                for m in sorted(self.modules, key=lambda mod: (mod.row, mod.col)):
                    w.writerow([m.row+1, m.col+1, m.width, m.code, m.label])
            messagebox.showinfo("CSV", f"Zapisano: {path}")
        except Exception as e:
            messagebox.showerror("CSV", f"Błąd zapisu: {e}")

    def save_png(self):
        # próba z PIL (ImageGrab)
        path = filedialog.asksaveasfilename(title="Zapisz PNG frontu", defaultextension=".png",
                                            filetypes=[("PNG","*.png")], initialfile="front_rozdzielnica.png")
        if not path:
            return
        try:
            from PIL import ImageGrab
            x = self.winfo_rootx() + self.canvas.winfo_x()
            y = self.winfo_rooty() + self.canvas.winfo_y()
            x1 = x + self.canvas.winfo_width()
            y1 = y + self.canvas.winfo_height()
            img = ImageGrab.grab().crop((x, y, x1, y1))
            img.save(path)
            messagebox.showinfo("PNG", f"Zapisano: {path}")
        except Exception as e:
            messagebox.showerror("PNG", f"Błąd zapisu PNG: {e}\nZainstaluj Pillow: pip install pillow")

    # ---------- Inne ----------
    def _apply_layout(self):
        choice = self.cmb_layout.get()
        old_rows, old_cols = self.rows, self.cols
        new_rows, new_cols = old_rows, old_cols

        if choice == "2×12":
            new_rows, new_cols = 2, 12
        elif choice == "3×18":
            new_rows, new_cols = 3, 18
        elif choice == "1×12":
            new_rows, new_cols = 1, 12
        else:
            # własny
            try:
                r = simpledialog.askinteger("Układ", "Liczba rzędów:", minvalue=1, maxvalue=8, initialvalue=self.rows)
                c = simpledialog.askinteger("Układ", "Liczba kolumn:", minvalue=4, maxvalue=36, initialvalue=self.cols)
                if r is None or c is None:
                    return
                new_rows, new_cols = r, c
            except:
                return

        if new_rows == old_rows and new_cols == old_cols:
            return

        if self.modules and not messagebox.askyesno(
            "Układ",
            "Zmiana układu usunie bieżący układ aparatów. Kontynuować?",
        ):
            return

        self.rows, self.cols = new_rows, new_cols
        self.modules.clear()
        self.draw_board()

    def _clear_all(self):
        if self.modules and not messagebox.askyesno("Wyczyść", "Usunąć wszystkie aparaty?"):
            return
        self.modules.clear()
        self.draw_board()

    def _click_canvas(self, event):
        # jeśli klik w puste pole (nie-numeracja), odpal _cell_clicked z obliczonym r,c
        r, c = self._rc_from_xy(event.x, event.y)
        if r is None or c is None:
            return
        # jeśli kliknięto obszar istniejącego modułu, przechwytuje to _edit_module poprzez tag
        self._cell_clicked(r, c)

    def _rc_from_xy(self, x: int, y: int) -> Tuple[Optional[int], Optional[int]]:
        # konwersja koordynatów na r/c
        for r in range(self.rows):
            y1 = PAD + r*(MOD_H + ROW_GAP)
            y2 = y1 + MOD_H
            if y1 <= y <= y2:
                c = (x - PAD) // MOD_W
                if 0 <= c < self.cols:
                    return r, int(c)
        return None, None


if __name__ == "__main__":
    app = RozdzielnicaApp()
    app.mainloop()
# ⏹ KONIEC KODU
