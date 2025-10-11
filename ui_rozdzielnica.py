"""PyQt6 dialog supporting assignment of circuits to RCD groups.

The previous implementation of :mod:`ui_rozdzielnica` relied on Tkinter.
That approach did not work together with the new PyQt-based main window –
attempting to open the dialog resulted in a runtime error because no Tk root
window existed.  This module provides a lightweight Qt alternative with a
similar API, returning structured information about the created RCD groups.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable as IterableABC, Mapping
from typing import Any, Dict, Iterable, Sequence

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class RozdzielnicaUI(QDialog):
    """Dialog służący do grupowania obwodów pod wspólne aparaty RCD.

    Parameters
    ----------
    obwody:
        Lista obiektów lub słowników opisujących obwody.  Każdy element
        powinien posiadać przynajmniej nazwę (`nazwa`).
    parent:
        Rodzic w drzewie Qt (opcjonalny).
    initial_groups:
        Wstępna konfiguracja grup RCD.  Funkcja obsługuje kilka formatów:

        - listę list nazw obwodów,
        - listę słowników ``{"name": <etykieta>, "circuits": [...]}``,
        - słownik ``{etykieta: [nazwy_obwodow]}`` lub ``{etykieta: [indeksy]}``.
    """

    _PLACEHOLDER = "— brak —"

    def __init__(
        self,
        obwody: Sequence[Any],
        *,
        parent: QWidget | None = None,
        initial_groups: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grupy RCD")
        self.resize(420, 360)

        self._obwody: Sequence[Any] = obwody
        self._initial_groups = initial_groups
        self._combos: list[QComboBox] = []
        self._group_names: list[str] = []
        self._prefill: Dict[int, str] = {}
        self._new_group_edit: QLineEdit | None = None
        self._result_groups: list[dict[str, Any]] = []

        self._prepare_initial_state()
        self._build_ui()

    # ------------------------------------------------------------------
    def exec(self) -> int:
        if not self._obwody:
            QMessageBox.information(
                self.parentWidget() or self,
                "Grupy RCD",
                "Brak obwodów do przypisania do grup RCD.",
            )
            self._result_groups = []
            return int(QDialog.DialogCode.Rejected)
        return super().exec()

    # ------------------------------------------------------------------
    def get_groups(self) -> list[dict[str, Any]]:
        """Zwróć informacje o grupach RCD.

        Każdy element listy ma postać ``{"name": <nazwa>, "circuits": [...]}``.
        Taka struktura jest prosta do serializacji, a jednocześnie łatwa do
        przetworzenia podczas generowania raportów.
        """

        return self._result_groups

    # ------------------------------------------------------------------
    def _prepare_initial_state(self) -> None:
        """Przygotuj listę dostępnych grup oraz prefille dla combo boxów."""

        names = [self._obwod_name(obw) for obw in self._obwody]

        def _ensure_group_name(name: str | None, position: int) -> str:
            label = name or f"RCD {position}"
            if label not in self._group_names:
                self._group_names.append(label)
            return label

        groups = self._initial_groups
        if isinstance(groups, Mapping):
            for idx, (name, members) in enumerate(groups.items(), start=1):
                label = _ensure_group_name(str(name), idx)
                for entry in self._iter_members(members):
                    if isinstance(entry, int) and 0 <= entry < len(names):
                        self._prefill[entry] = label
                    elif isinstance(entry, str) and entry in names:
                        self._prefill[names.index(entry)] = label
        elif isinstance(groups, IterableABC):
            for idx, group in enumerate(groups, start=1):
                if isinstance(group, Mapping):
                    label = _ensure_group_name(
                        self._first_of(group, "name", "label", "title"),
                        idx,
                    )
                    members = group.get("circuits") or group.get("obwody") or group
                else:
                    label = _ensure_group_name(None, idx)
                    members = group
                for entry in self._iter_members(members):
                    if isinstance(entry, int) and 0 <= entry < len(names):
                        self._prefill[entry] = label
                    elif isinstance(entry, str) and entry in names:
                        self._prefill[names.index(entry)] = label

        if not self._group_names and self._obwody:
            self._group_names = ["RCD 1", "RCD 2"]

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(
            "Wybierz grupę RCD dla każdego obwodu (pozostaw \n"
            "pole puste, aby nie przypisywać obwodu)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        grid = QGridLayout(scroll_widget)
        grid.setColumnStretch(1, 1)

        for row, obw in enumerate(self._obwody):
            label = QLabel(self._format_obwod_label(obw, row))
            combo = QComboBox()
            combo.addItem(self._PLACEHOLDER)
            for name in self._group_names:
                combo.addItem(name)
            if row in self._prefill:
                combo.setCurrentText(self._prefill[row])
            self._combos.append(combo)

            grid.addWidget(label, row, 0)
            grid.addWidget(combo, row, 1)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Dodaj grupę:"))
        self._new_group_edit = QLineEdit()
        self._new_group_edit.setPlaceholderText("np. RCD kuchnia")
        add_button = QPushButton("Dodaj")
        add_button.clicked.connect(self._add_group)
        add_layout.addWidget(self._new_group_edit)
        add_layout.addWidget(add_button)
        layout.addLayout(add_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _add_group(self) -> None:
        if self._new_group_edit is None:
            return
        name = self._new_group_edit.text().strip()
        if not name:
            return
        if name not in self._group_names:
            self._group_names.append(name)
            for combo in self._combos:
                combo.addItem(name)
        self._new_group_edit.clear()

    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        grouped: "OrderedDict[str, list[str]]" = OrderedDict()
        for idx, combo in enumerate(self._combos):
            choice = combo.currentText()
            if not choice or choice == self._PLACEHOLDER:
                continue
            label = choice.strip()
            if not label:
                continue
            grouped.setdefault(label, []).append(self._obwod_name(self._obwody[idx]))

        self._result_groups = [
            {"name": name, "circuits": members}
            for name, members in grouped.items()
        ]
        self.accept()

    # ------------------------------------------------------------------
    @staticmethod
    def _obwod_name(obw: Any) -> str:
        if isinstance(obw, Mapping):
            name = obw.get("nazwa") or obw.get("name")
            if name:
                return str(name)
        name = getattr(obw, "nazwa", None) or getattr(obw, "name", None)
        if name:
            return str(name)
        return "Nieznany obwód"

    @classmethod
    def _format_obwod_label(cls, obw: Any, idx: int) -> str:
        base = cls._obwod_name(obw)
        zabezpieczenie = None
        if isinstance(obw, Mapping):
            zabezpieczenie = obw.get("zabezpieczenie")
        else:
            zabezpieczenie = getattr(obw, "zabezpieczenie", None)
        if zabezpieczenie:
            return f"{base} ({zabezpieczenie})"
        if base == "Nieznany obwód":
            return f"Obwód {idx + 1}"
        return base

    @staticmethod
    def _iter_members(raw: Any) -> Iterable[Any]:
        if raw is None:
            return []
        if isinstance(raw, Mapping):
            members = raw.get("circuits") or raw.get("obwody") or raw.get("items")
            return members if members is not None else []
        if isinstance(raw, (str, bytes)):
            return [raw]
        if isinstance(raw, IterableABC):
            return raw
        return []

    @staticmethod
    def _first_of(mapping: Mapping[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = mapping.get(key)
            if value:
                return str(value)
        return None

