# elektryk.py
# Domowy Elektryk – wersja PyQt6 (2025-10)
# -----------------------------------------
# Uproszczony projekt do planowania instalacji elektrycznej
# Autor: Edwin K. + GPT-5 (projekt Codex)
# -----------------------------------------

import sys, json, os
from elektryk_report import generate_all_reports
from elektryk_icons import icon_label, ICON_MAP
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsItem, QGraphicsTextItem, QFileDialog, QMessageBox,
    QVBoxLayout, QWidget, QListWidget, QPushButton, QHBoxLayout, QLabel,
    QInputDialog, QDialog, QComboBox, QFormLayout, QLineEdit, QTextEdit
)
from PyQt6.QtGui import QPen, QColor, QBrush, QAction
from PyQt6.QtCore import Qt, QRectF, QPointF

# -------------------------------
# Stałe i ścieżki
# -------------------------------
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
PROJECT_PATH = os.path.join(DATA_DIR, "projekt_domowy.json")

OBWOD_COLORS = [
    "#1976d2",
    "#43a047",
    "#f4511e",
    "#8e24aa",
    "#00897b",
    "#5d4037",
    "#3949ab",
    "#fdd835",
]

# -------------------------------
# Klasy pomocnicze
# -------------------------------
class ElektrykElement(QGraphicsRectItem):
    def __init__(
        self,
        typ,
        x,
        y,
        obwod=None,
        kolor="#e0e0e0",
        nr=None,
        grid_size=20,
        snap_enabled=True,
    ):
        super().__init__(0, 0, 34, 34)
        self.typ = self._normalize_type(typ)
        self.base_type = self.typ
        self.obwod = obwod
        self.kolor = kolor
        self.nr = nr or ""
        self.grid_size = grid_size
        self.snap_enabled = snap_enabled
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(self.kolor)))
        self.setPen(QPen(Qt.GlobalColor.black))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(Qt.GlobalColor.black)
        self.text.setPos(2, 4)
        self.setZValue(1)
        self._update_label()

    @staticmethod
    def _normalize_type(typ):
        if typ in ICON_MAP:
            return typ
        for key in ICON_MAP:
            if key and key in typ:
                return key
        return typ

    def _compose_label(self):
        label = icon_label(self.typ) if self.typ in ICON_MAP else str(self.typ)
        if self.nr:
            label = f"{label}\n{self.nr}"
        return label

    def _tooltip(self):
        lines = [icon_label(self.typ) if self.typ in ICON_MAP else str(self.typ)]
        if self.nr:
            lines.append(f"Nr: {self.nr}")
        if self.obwod:
            lines.append(f"Obwód: {self.obwod}")
        return "\n".join(lines)

    def _update_label(self):
        self.text.setPlainText(self._compose_label())
        self.setToolTip(self._tooltip())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.snap_enabled:
            snapped = self._snap_point(value)
            return snapped
        return super().itemChange(change, value)

    def _snap_point(self, point):
        x = round(point.x() / self.grid_size) * self.grid_size
        y = round(point.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)

    def to_dict(self):
        return {
            "typ": self.typ,
            "x": self.x(),
            "y": self.y(),
            "obwod": self.obwod,
            "kolor": self.kolor,
            "nr": self.nr,
        }

# -------------------------------
# Okno Rozdzielnicy
# -------------------------------
class RozdzielnicaWindow(QDialog):
    def __init__(self, obwody):
        super().__init__()
        self.setWindowTitle("Rozdzielnica - grupowanie RCD")
        self.resize(400, 400)
        layout = QVBoxLayout()
        self.list = QTextEdit()
        self.list.setReadOnly(True)
        layout.addWidget(QLabel("Obwody i przypisane RCD:"))
        layout.addWidget(self.list)
        self.setLayout(layout)
        self.update_view(obwody)

    def update_view(self, obwody):
        tekst = ""
        for i, obw in enumerate(obwody, 1):
            rcd = f"RCD-{(i - 1) // 4 + 1}"  # co 4 obwody nowy RCD
            tekst += f"{obw['nazwa']}  →  {rcd}\n"
        self.list.setText(tekst)

# -------------------------------
# Główne okno programu
# -------------------------------
class ElektrykApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Domowy Elektryk – PyQt6")
        self.resize(1000, 600)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.scene.setBackgroundBrush(QBrush(QColor("#f9f9f9")))
        self.scene.setSceneRect(QRectF(0, 0, 1600, 1000))

        self.grid_size = 40
        self.snap_to_grid = True
        self.grid_lines = []
        self.obwody = []
        self.elements = []
        self.rcd_groups = []

        self._create_menu()
        self._init_ui()
        self._draw_grid()
        self._load_project()
        self.statusBar().showMessage("Gotowe", 0)

    # ---------------------------
    # UI
    # ---------------------------
    def _init_ui(self):
        main_widget = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(self.view, 3)

        sidebar = QVBoxLayout()
        self.list_obwody = QListWidget()
        sidebar.addWidget(QLabel("Obwody:"))
        sidebar.addWidget(self.list_obwody)

        btn_add_obw = QPushButton("➕ Dodaj obwód")
        btn_add_gniazdo = QPushButton("⚡ Dodaj gniazdko")
        btn_add_lampa = QPushButton("💡 Dodaj lampę")
        btn_rozdzielnica = QPushButton("🔌 Rozdzielnica")
        btn_zapisz = QPushButton("💾 Zapisz projekt")
        btn_raport = QPushButton("📄 Raport TXT")

        btn_add_obw.clicked.connect(self.add_obwod)
        btn_add_gniazdo.clicked.connect(lambda: self.add_element("Gniazdko"))
        btn_add_lampa.clicked.connect(lambda: self.add_element("Lampa"))
        btn_rozdzielnica.clicked.connect(self.open_rozdzielnica)
        btn_zapisz.clicked.connect(self._save_project)
        btn_raport.clicked.connect(self.export_report)

        for b in [btn_add_obw, btn_add_gniazdo, btn_add_lampa, btn_rozdzielnica, btn_zapisz, btn_raport]:
            sidebar.addWidget(b)

        sidebar.addStretch()
        layout.addLayout(sidebar, 1)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def _create_menu(self):
        bar = self.menuBar()
        view_menu = bar.addMenu("Widok")
        self.action_snap = QAction("Przyciągaj do siatki", self)
        self.action_snap.setCheckable(True)
        self.action_snap.setChecked(True)
        self.action_snap.toggled.connect(self.toggle_snap)
        view_menu.addAction(self.action_snap)

    def _draw_grid(self):
        for line in self.grid_lines:
            self.scene.removeItem(line)
        self.grid_lines = []
        pen = QPen(QColor("#e0e0e0"))
        pen.setCosmetic(True)
        rect = self.scene.sceneRect()
        width = int(rect.width())
        height = int(rect.height())
        for x in range(0, width + 1, self.grid_size):
            line = self.scene.addLine(x, 0, x, height, pen)
            line.setZValue(-10)
            line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.grid_lines.append(line)
        for y in range(0, height + 1, self.grid_size):
            line = self.scene.addLine(0, y, width, y, pen)
            line.setZValue(-10)
            line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.grid_lines.append(line)

    # ---------------------------
    # Dodawanie obwodów
    # ---------------------------
    def add_obwod(self):
        nazwa, ok = QInputDialog.getText(self, "Nowy obwód", "Podaj nazwę obwodu:")
        if ok and nazwa:
            kolor = OBWOD_COLORS[len(self.obwody) % len(OBWOD_COLORS)]
            nowy = {
                "nazwa": nazwa,
                "przekroj": "3x2,5",
                "dlugosc": 0,
                "zabezpieczenie": "B16",
                "kolor": kolor,
            }
            self.obwody.append(nowy)
            self.refresh_obwody()

    def refresh_obwody(self):
        self.list_obwody.clear()
        for obw in self.obwody:
            self.list_obwody.addItem(f"{obw['nazwa']} ({obw['zabezpieczenie']})")

    # ---------------------------
    # Dodawanie elementów
    # ---------------------------
    def add_element(self, typ):
        if not self.obwody:
            QMessageBox.information(self, "Brak obwodów", "Dodaj najpierw obwód.")
            return

        wybory = [o["nazwa"] for o in self.obwody] + ["➕ Nowy obwód"]
        obwod, ok = QInputDialog.getItem(self, "Wybierz obwód", "Do którego obwodu dodać?", wybory, 0, False)
        if not ok:
            return

        if obwod == "➕ Nowy obwód":
            self.add_obwod()
            obwod = self.obwody[-1]["nazwa"]
        kolor = self._color_for_obwod(obwod)
        prefix = {
            "Gniazdko": "G",
            "Lampa": "L",
            "Rozdzielnica": "R",
            "Włącznik": "W",
        }.get(typ, typ[:1].upper())
        existing = sum(1 for e in self.elements if self._element_base_type(e) == typ)
        nr = f"{prefix}-{existing + 1:02d}"
        base_x = 120 + len(self.elements) * 36
        base_y = 120 + len(self.elements) * 24
        if self.snap_to_grid:
            snapped = self._snap_point(QPointF(base_x, base_y))
            base_x, base_y = snapped.x(), snapped.y()
        el = ElektrykElement(
            typ,
            base_x,
            base_y,
            obwod,
            kolor=kolor,
            nr=nr,
            grid_size=self.grid_size,
            snap_enabled=self.snap_to_grid,
        )
        self.scene.addItem(el)
        self.elements.append(el)

    # ---------------------------
    # Rozdzielnica
    # ---------------------------
    def open_rozdzielnica(self):
        dlg = RozdzielnicaWindow(self.obwody)
        dlg.exec()

    # ---------------------------
    # Zapis / odczyt
    # ---------------------------
    def _save_project(self):
        data = {
            "obwody": self.obwody,
            "elementy": [e.to_dict() for e in self.elements]
        }
        with open(PROJECT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "Zapisano", f"Projekt zapisany w {PROJECT_PATH}")

    def _load_project(self):
        if os.path.exists(PROJECT_PATH):
            try:
                with open(PROJECT_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.obwody = data.get("obwody", [])
                for idx, obw in enumerate(self.obwody):
                    if "kolor" not in obw:
                        obw["kolor"] = OBWOD_COLORS[idx % len(OBWOD_COLORS)]
                self.refresh_obwody()
                for e in data.get("elementy", []):
                    typ = e.get("typ", "Element")
                    kolor = e.get("kolor", self._color_for_obwod(e.get("obwod")))
                    el = ElektrykElement(
                        typ,
                        e["x"],
                        e["y"],
                        e.get("obwod"),
                        kolor=kolor,
                        nr=e.get("nr"),
                        grid_size=self.grid_size,
                        snap_enabled=self.snap_to_grid,
                    )
                    self.scene.addItem(el)
                    self.elements.append(el)
            except Exception as ex:
                print("Błąd wczytania projektu:", ex)

    # ---------------------------
    # Raport TXT
    # ---------------------------
    def export_report(self):
        msg = generate_all_reports(self.obwody, self.elements, self.rcd_groups)
        QMessageBox.information(self, "Raporty", msg)

    # ---------------------------
    # Zamknięcie programu
    # ---------------------------
    def closeEvent(self, event):
        self._save_project()
        event.accept()

    def _color_for_obwod(self, obwod):
        for idx, item in enumerate(self.obwody):
            if item["nazwa"] == obwod:
                kolor = item.get("kolor")
                if not kolor:
                    kolor = OBWOD_COLORS[idx % len(OBWOD_COLORS)]
                    item["kolor"] = kolor
                return kolor
        return "#e0e0e0"

    def _element_base_type(self, element):
        if hasattr(element, "base_type"):
            return element.base_type
        typ = getattr(element, "typ", "")
        for key in ICON_MAP:
            if key in typ:
                return key
        return typ

    def _snap_point(self, point: QPointF) -> QPointF:
        x = round(point.x() / self.grid_size) * self.grid_size
        y = round(point.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)

    def toggle_snap(self, checked: bool):
        self.snap_to_grid = bool(checked)
        for element in self.elements:
            element.snap_enabled = self.snap_to_grid
            element.grid_size = self.grid_size
            if self.snap_to_grid:
                snapped = self._snap_point(element.pos())
                element.setPos(snapped)
        status = "ON" if self.snap_to_grid else "OFF"
        self.statusBar().showMessage(f"Przyciąganie do siatki: {status}", 3000)

# -------------------------------
# Start programu
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ElektrykApp()
    win.show()
    sys.exit(app.exec())
