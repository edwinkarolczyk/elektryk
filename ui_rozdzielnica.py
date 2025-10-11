"""Dialog pomocniczy do zarządzania grupami RCD."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk, messagebox


class RozdzielnicaUI:
    """Prosty edytor grup RCD oparty o Tkinter.

    Dialog pozwala przypisać każdy obwód (lista obiektów z atrybutami
    ``nr`` oraz ``opis``) do nazwanej grupy RCD. Wynik zwracany przez
    :meth:`get_groups` to słownik ``{nazwa_grupy: [indeksy_obwodow]}``.
    """

    def __init__(
        self,
        obwody: List[Any],
        *,
        parent: Optional[tk.Misc] = None,
        initial_groups: Optional[Dict[str, List[int]]] = None,
    ) -> None:
        self.obwody = obwody
        self.parent = parent or tk._default_root  # type: ignore[attr-defined]
        if self.parent is None:
            raise RuntimeError("RozdzielnicaUI wymaga aktywnego okna nadrzędnego")

        filtered: Dict[str, List[int]] = {}
        if initial_groups:
            for name, idxs in initial_groups.items():
                valid = [i for i in idxs if 0 <= i < len(self.obwody)]
                if valid:
                    filtered[name] = valid
        self._prefill: Dict[int, str] = {}
        for name, idxs in filtered.items():
            for idx in idxs:
                self._prefill[idx] = name

        seen: set[str] = set()
        self._group_options: List[str] = []
        for name in filtered.keys():
            if name not in seen:
                seen.add(name)
                self._group_options.append(name)
        if not self._group_options and self.obwody:
            self._group_options = ["RCD 1", "RCD 2"]

        self._groups: Dict[str, List[int]] = filtered
        self._result = False
        self._dialog: Optional[tk.Toplevel] = None
        self._group_vars: List[tk.StringVar] = []
        self._combo_boxes: List[ttk.Combobox] = []
        self._entry_new_group: Optional[ttk.Entry] = None

    # ------------------------------------------------------------------
    def exec(self) -> bool:
        if not self.obwody:
            messagebox.showinfo(
                "Grupy RCD",
                "Brak obwodów do przypisania do grup RCD.",
                parent=self.parent,
            )
            self._groups = {}
            self._result = False
            return False

        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Grupy RCD")
        self._dialog.transient(self.parent)
        self._dialog.grab_set()
        self._dialog.resizable(False, True)
        self._dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frm = ttk.Frame(self._dialog, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Wybierz grupę RCD dla każdego obwodu (puste = brak przypisania).",
        ).pack(anchor="w")

        list_frame = ttk.Frame(frm)
        list_frame.pack(fill="both", expand=True, pady=(8, 0))

        max_height = min(360, 36 * len(self.obwody) + 30)
        canvas = tk.Canvas(list_frame, highlightthickness=0, height=max_height)
        vscroll = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        ttk.Label(inner, text="Obwód", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(inner, text="Grupa RCD", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=1, sticky="w", padx=(12, 0)
        )

        for row, obw in enumerate(self.obwody, start=1):
            label = self._format_obwod(obw, row)
            ttk.Label(inner, text=label).grid(row=row, column=0, sticky="w", pady=2)

            var = tk.StringVar(value=self._prefill.get(row - 1, ""))
            combo = ttk.Combobox(
                inner,
                textvariable=var,
                values=self._combo_values(),
                width=24,
                state="normal",
            )
            combo.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=2)
            self._group_vars.append(var)
            self._combo_boxes.append(combo)

        add_frame = ttk.Frame(frm)
        add_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(add_frame, text="Dodaj grupę:").pack(side="left")
        self._entry_new_group = ttk.Entry(add_frame, width=18)
        self._entry_new_group.pack(side="left", padx=(6, 6))
        ttk.Button(add_frame, text="Dodaj", command=self._add_group).pack(side="left")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(12, 0))
        ttk.Button(btns, text="Anuluj", command=self._on_cancel).pack(
            side="right", padx=4
        )
        ttk.Button(btns, text="Zapisz", command=self._on_save).pack(
            side="right", padx=4
        )

        self._dialog.bind("<Return>", lambda _e: self._on_save())
        self._dialog.bind("<Escape>", lambda _e: self._on_cancel())

        self.parent.wait_window(self._dialog)
        return self._result

    # ------------------------------------------------------------------
    def get_groups(self) -> Dict[str, List[int]]:
        return self._groups

    # ------------------------------------------------------------------
    def _combo_values(self) -> tuple[str, ...]:
        return ("", *self._group_options)

    def _format_obwod(self, obw: Any, idx: int) -> str:
        nr = getattr(obw, "nr", "")
        opis = getattr(obw, "opis", "")
        label = " ".join(part for part in (nr, opis) if part).strip()
        return label or f"Obwód {idx}"

    def _add_group(self) -> None:
        if not self._entry_new_group:
            return
        name = self._entry_new_group.get().strip()
        if not name:
            return
        if name not in self._group_options:
            self._group_options.append(name)
            values = self._combo_values()
            for combo in self._combo_boxes:
                combo.configure(values=values)
        self._entry_new_group.delete(0, "end")

    def _on_save(self) -> None:
        groups: Dict[str, List[int]] = {}
        for idx, var in enumerate(self._group_vars):
            name = var.get().strip()
            if not name:
                continue
            groups.setdefault(name, []).append(idx)
        self._groups = groups
        self._result = True
        if self._dialog is not None:
            self._dialog.destroy()

    def _on_cancel(self) -> None:
        self._result = False
        if self._dialog is not None:
            self._dialog.destroy()
