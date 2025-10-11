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
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QRectF

# -------------------------------
# Stałe i ścieżki
# -------------------------------
DATA_DIR = "data"
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
PROJECT_PATH = os.path.join(DATA_DIR, "projekt_domowy.json")

# -------------------------------
# Klasy pomocnicze
# -------------------------------
class ElektrykElement(QGraphicsRectItem):
    def __init__(self, typ, x, y, obwod=None):
        super().__init__(0, 0, 30, 30)
        self.typ = typ
        self.obwod = obwod
        self.setPos(x, y)
        self.setBrush(QBrush(QColor("#e0e0e0")))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.text = QGraphicsTextItem(self.typ, self)
        self.text.setDefaultTextColor(Qt.GlobalColor.black)
        self.text.setPos(5, 5)

    def to_dict(self):
        return {
            "typ": self.typ,
            "x": self.x(),
            "y": self.y(),
            "obwod": self.obwod
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

        self.obwody = []
        self.elements = []

        self._init_ui()
        self._load_project()

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

    # ---------------------------
    # Dodawanie obwodów
    # ---------------------------
    def add_obwod(self):
        nazwa, ok = QInputDialog.getText(self, "Nowy obwód", "Podaj nazwę obwodu:")
        if ok and nazwa:
            nowy = {"nazwa": nazwa, "przekroj": "3x2,5", "dlugosc": 0, "zabezpieczenie": "B16"}
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

        el = ElektrykElement(icon_label(typ), 50 + len(self.elements)*40, 50 + len(self.elements)*20, obwod)
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
                for e in data.get("elementy", []):
                    typ = e.get("typ", "Element")
                    if typ in ICON_MAP:
                        typ = icon_label(typ)
                    el = ElektrykElement(typ, e["x"], e["y"], e.get("obwod"))
                    self.scene.addItem(el)
                    self.elements.append(el)
                self.refresh_obwody()
            except Exception as ex:
                print("Błąd wczytania projektu:", ex)

    # ---------------------------
    # Raport TXT
    # ---------------------------
    def export_report(self):
        msg = generate_all_reports(self.obwody, self.elements, getattr(self, "rcd_groups", None))
        QMessageBox.information(self, "Raporty", msg)

    # ---------------------------
    # Zamknięcie programu
    # ---------------------------
    def closeEvent(self, event):
        self._save_project()
        event.accept()

# -------------------------------
# Start programu
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ElektrykApp()
    win.show()
    sys.exit(app.exec())
