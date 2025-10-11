"""Cable sizing helper dialog for the Elektryka Tkinter application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class CableCalculatorDialog(tk.Toplevel):
    """Simple dialog that estimates current, voltage drop and cable size."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.title("Kalkulator przewodów")
        self.transient(master)
        self.resizable(False, False)
        self.grab_set()

        self.columnconfigure(0, weight=1)

        main = ttk.Frame(self, padding=12)
        main.grid(sticky="nsew")

        self.length_var = tk.StringVar()
        self.power_var = tk.StringVar()
        self.voltage_var = tk.StringVar(value="230")

        form = ttk.Frame(main)
        form.grid(row=0, column=0, sticky="nsew")

        ttk.Label(form, text="Długość kabla [m]:").grid(row=0, column=0, sticky="w", pady=(0, 6))
        length_entry = ttk.Entry(form, textvariable=self.length_var, width=12)
        length_entry.grid(row=0, column=1, sticky="we", padx=(8, 0), pady=(0, 6))

        ttk.Label(form, text="Moc obciążenia [W]:").grid(row=1, column=0, sticky="w", pady=6)
        power_entry = ttk.Entry(form, textvariable=self.power_var, width=12)
        power_entry.grid(row=1, column=1, sticky="we", padx=(8, 0), pady=6)

        ttk.Label(form, text="Napięcie [V]:").grid(row=2, column=0, sticky="w", pady=6)
        voltage_entry = ttk.Entry(form, textvariable=self.voltage_var, width=12)
        voltage_entry.grid(row=2, column=1, sticky="we", padx=(8, 0), pady=6)

        button = ttk.Button(main, text="Oblicz", command=self._calculate)
        button.grid(row=1, column=0, pady=(12, 6), sticky="we")

        self.result_var = tk.StringVar(value="Wynik: ---")
        ttk.Label(main, textvariable=self.result_var, wraplength=320).grid(row=2, column=0, sticky="we")

        self.bind("<Return>", lambda _event: self._calculate())
        self.bind("<Escape>", lambda _event: self.destroy())

        length_entry.focus_set()

    def _calculate(self) -> None:
        try:
            cable_length = float(self.length_var.get())
            power = float(self.power_var.get())
            voltage = float(self.voltage_var.get())
        except ValueError:
            self.result_var.set("Błąd danych.")
            return

        if voltage <= 0:
            self.result_var.set("Napięcie musi być dodatnie.")
            return

        current = power / voltage

        # Resistance of copper conductor (Ohm·mm²/m) ~ 0.0175
        # Reference cross-section 1.5 mm² and conductivity 56 (MS/m) as in original dialog.
        voltage_drop_percent = (2 * cable_length * current * 0.0175) / (1.5 * 56) * 100

        if current <= 10:
            cross_section = "1.5 mm²"
        elif current <= 16:
            cross_section = "2.5 mm²"
        else:
            cross_section = "4 mm²"

        self.result_var.set(
            f"I = {current:.2f} A, spadek ≈ {voltage_drop_percent:.2f}%, "
            f"zalecany przewód: {cross_section}"
        )

