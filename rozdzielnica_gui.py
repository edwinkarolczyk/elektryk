# Domowy Elektryk — Rozdzielnica realistyczna (v1.5.0)
# Klikany widok 2x12 modułów DIN
# Autor: ChatGPT Codex (2025-10-08)

import json
import os
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, messagebox

MODULE_TYPES = [
    ("FR - Wyłącznik główny", "FR"),
    ("RCD 30mA - Różnicówka", "RCD"),
    ("MCB B10", "B10"),
    ("MCB B16", "B16"),
    ("MCB C20", "C20"),
    ("SPD - Ochronnik przepięć", "SPD"),
    ("PSU 24V - Zasilacz", "PSU"),
    ("PLC - Sterownik", "PLC"),
    ("RELAY - Przekaźnik", "RELAY"),
    ("PUSTE MIEJSCE", "")
]


class RozdzielnicaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Domowy Elektryk — Rozdzielnica 2x12")
        self.geometry("960x400")
        self.resizable(False, False)
        self.rows, self.cols = 2, 12
        self.modules = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        self.status_var = tk.StringVar(value="Gotowe")
        self._build_ui()
        self.draw_board()

    def _build_ui(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Rozdzielnica 2×12 (kliknij moduł by wybrać aparat)",
            font=("Segoe UI", 10, "bold"),
        ).pack(pady=6)
        self.canvas = tk.Canvas(
            frame,
            width=880,
            height=320,
            bg="#f4f4f4",
            highlightthickness=1,
            highlightbackground="#999",
        )
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_click)

        btn_bar = ttk.Frame(frame)
        btn_bar.pack(pady=(0, 6))
        ttk.Button(
            btn_bar,
            text="Zapisz do pliku (front.png)",
            command=self.save_screenshot,
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_bar,
            text="Zapisz układ (.json)",
            command=self.save_layout,
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_bar,
            text="Wczytaj układ…",
            command=self.load_layout,
        ).pack(side="left", padx=4)

        ttk.Label(frame, textvariable=self.status_var, foreground="#555").pack(pady=(0, 10))

    def draw_board(self):
        self.canvas.delete("all")
        pad = 20
        mod_w, mod_h = 60, 70
        gap_y = 10
        # ramka
        self.canvas.create_rectangle(
            pad - 8,
            pad - 8,
            pad + self.cols * mod_w + 8,
            pad + self.rows * (mod_h + gap_y) - gap_y + 8,
            outline="#444",
            width=2,
            fill="#e5e5e5",
        )
        for r in range(self.rows):
            y = pad + r * (mod_h + gap_y)
            # szyna DIN (symboliczna)
            self.canvas.create_rectangle(
                pad,
                y + 8,
                pad + self.cols * mod_w,
                y + 12,
                fill="#bbb",
                outline="",
            )
            for c in range(self.cols):
                x = pad + c * mod_w
                tag = f"cell-{r}-{c}"
                self.canvas.create_rectangle(
                    x,
                    y,
                    x + mod_w,
                    y + mod_h,
                    outline="#000",
                    fill="#ffffff",
                    tags=tag,
                )
                self.canvas.tag_bind(
                    tag, "<Button-1>", lambda e, rr=r, cc=c: self.cell_click(rr, cc)
                )
                label = self.modules[r][c]
                if label:
                    # górna kreska ciemniejsza (maskownica)
                    self.canvas.create_rectangle(
                        x,
                        y,
                        x + mod_w,
                        y + 10,
                        fill="#ddd",
                        outline="#ddd",
                    )
                    self.canvas.create_text(
                        x + mod_w / 2,
                        y + mod_h / 2,
                        text=label,
                        font=("Segoe UI", 9, "bold"),
                    )
                # numeracja u dołu
                if r == self.rows - 1:
                    self.canvas.create_text(
                        x + mod_w / 2,
                        y + mod_h + 10,
                        text=str(c + 1),
                        fill="#444",
                        font=("Segoe UI", 8),
                    )

    def cell_click(self, row, col):
        top = tk.Toplevel(self)
        top.title("Wybierz aparat")
        top.geometry("240x260")
        lb = tk.Listbox(top, font=("Segoe UI", 10))
        for name, code in MODULE_TYPES:
            lb.insert("end", name)
        lb.pack(fill="both", expand=True, padx=6, pady=6)

        def ok():
            sel = lb.curselection()
            if not sel:
                top.destroy()
                return
            _, code = MODULE_TYPES[sel[0]]
            label = simpledialog.askstring(
                "Etykieta",
                f"Etykieta dla {code or 'PUSTE'}:",
                initialvalue=code,
                parent=top,
            )
            self.modules[row][col] = label or ""
            self.draw_board()
            self.set_status(
                f"Ustawiono moduł ({row + 1}, {col + 1}) na '{self.modules[row][col] or 'PUSTE'}'"
            )
            top.destroy()

        ttk.Button(top, text="OK", command=ok).pack(pady=6)
        ttk.Button(top, text="Anuluj", command=top.destroy).pack()

    def on_click(self, event):
        pass  # kliknięcia obsługuje cell_click()

    def save_screenshot(self):
        try:
            from PIL import ImageGrab

            x = self.winfo_rootx() + self.canvas.winfo_x()
            y = self.winfo_rooty() + self.canvas.winfo_y()
            x1 = x + self.canvas.winfo_width()
            y1 = y + self.canvas.winfo_height()
            img = ImageGrab.grab().crop((x, y, x1, y1))
            img.save("front.png")
            print("[OK] Zapisano front.png")
            self.set_status("Zapisano obraz front.png")
        except Exception as e:  # pragma: no cover - zależne od środowiska GUI
            print("[ERROR]", e)
            messagebox.showerror("Błąd zapisu", str(e))
            self.set_status("Nie udało się zapisać front.png")

    def save_layout(self):
        path = filedialog.asksaveasfilename(
            title="Zapisz układ",
            defaultextension=".json",
            filetypes=[("Plik JSON", "*.json"), ("Wszystkie pliki", "*")],
            initialfile="rozdzielnica.json",
        )
        if not path:
            return
        data = {
            "rows": self.rows,
            "cols": self.cols,
            "modules": self.modules,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.set_status(f"Zapisano układ do {os.path.basename(path)}")
        except OSError as exc:
            messagebox.showerror("Błąd zapisu", str(exc))
            self.set_status("Nie udało się zapisać układu")

    def load_layout(self):
        path = filedialog.askopenfilename(
            title="Wczytaj układ",
            filetypes=[("Plik JSON", "*.json"), ("Wszystkie pliki", "*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Błąd wczytywania", f"Nie można wczytać pliku:\n{exc}")
            self.set_status("Nie udało się wczytać układu")
            return

        modules = data.get("modules")
        if not self._validate_modules(modules):
            messagebox.showerror(
                "Błędny układ", "Plik nie zawiera poprawnego układu 2x12."
            )
            self.set_status("Nie udało się wczytać układu")
            return

        self.modules = [[str(cell) if cell else "" for cell in row] for row in modules]
        self.draw_board()
        self.set_status(f"Wczytano układ z {os.path.basename(path)}")

    def _validate_modules(self, modules):
        if not isinstance(modules, list) or len(modules) != self.rows:
            return False
        for row in modules:
            if not isinstance(row, list) or len(row) != self.cols:
                return False
        return True

    def set_status(self, message):
        self.status_var.set(message)


if __name__ == "__main__":
    app = RozdzielnicaApp()
    app.mainloop()
# ⏹ KONIEC KODU
