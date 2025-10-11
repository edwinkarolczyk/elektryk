"""
Moduł raportów dla programu "Domowy Elektryk".
Odpowiada za generowanie raportów w formatach TXT, CSV oraz – jeśli jest
zainstalowany reportlab – PDF.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Iterable

try:  # Opcjonalna zależność wykorzystywana tylko do PDF
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover - zależność zewnętrzna
    REPORTLAB_AVAILABLE = False

DATA_DIR = "data"


def _ensure_data_dir() -> None:
    """Utwórz katalog na raporty, jeśli jeszcze nie istnieje."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _count_elements(obwod: str, elements: Iterable) -> int:
    """Zlicz elementy przypisane do konkretnego obwodu."""

    def _element_circuit(element) -> str | None:
        if isinstance(element, dict):
            return element.get("obwod")
        return getattr(element, "obwod", None)

    return sum(1 for element in elements if _element_circuit(element) == obwod)


def _assigned_rcd_label(obwod: str, rcd_groups: Iterable[Iterable[str]] | None) -> str:
    """Zwróć etykietę grupy RCD, jeżeli obwód do niej należy."""
    if not rcd_groups:
        return "-"

    for index, group in enumerate(rcd_groups, start=1):
        if obwod in group:
            return f"RCD-{index}"
    return "-"


# -----------------------------------------
# Funkcja: generuj raport TXT
# -----------------------------------------
def generate_txt(obwody, elements, rcd_groups=None):
    _ensure_data_dir()
    raport_path = os.path.join(DATA_DIR, "raport.txt")
    lines = []
    lines.append("RAPORT INSTALACJI ELEKTRYCZNEJ")
    lines.append("=" * 40)
    lines.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    for obw in obwody:
        name = obw["nazwa"]
        el_count = _count_elements(name, elements)
        lines.append(f"Obwód: {name}")
        lines.append(f"  Zabezpieczenie: {obw['zabezpieczenie']}")
        lines.append(f"  Przekrój: {obw['przekroj']}")
        lines.append(f"  Długość: {obw['dlugosc']} m")
        lines.append(f"  Liczba elementów: {el_count}")
        lines.append(f"  Grupa RCD: {_assigned_rcd_label(name, rcd_groups)}")
        lines.append("")

    with open(raport_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))
    return raport_path


# -----------------------------------------
# Funkcja: generuj raport CSV
# -----------------------------------------
def generate_csv(obwody, elements, rcd_groups=None):
    _ensure_data_dir()
    raport_path = os.path.join(DATA_DIR, "raport.csv")
    with open(raport_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        header = [
            "Nazwa obwodu",
            "Zabezpieczenie",
            "Przekrój",
            "Długość [m]",
            "Liczba elementów",
            "RCD",
        ]
        writer.writerow(header)
        for obw in obwody:
            name = obw["nazwa"]
            el_count = _count_elements(name, elements)
            rcd = _assigned_rcd_label(name, rcd_groups)
            writer.writerow(
                [
                    name,
                    obw["zabezpieczenie"],
                    obw["przekroj"],
                    obw["dlugosc"],
                    el_count,
                    rcd,
                ]
            )
    return raport_path


# -----------------------------------------
# Funkcja: generuj raport PDF
# -----------------------------------------
def generate_pdf(obwody, elements, rcd_groups=None):
    if not REPORTLAB_AVAILABLE:
        return None

    _ensure_data_dir()
    raport_path = os.path.join(DATA_DIR, "raport.pdf")
    pdf_canvas = canvas.Canvas(raport_path, pagesize=A4)
    _, height = A4
    y_position = height - 60
    pdf_canvas.setFont("Helvetica-Bold", 14)
    pdf_canvas.drawString(50, y_position, "RAPORT INSTALACJI ELEKTRYCZNEJ")
    y_position -= 20
    pdf_canvas.setFont("Helvetica", 10)
    pdf_canvas.drawString(50, y_position, f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y_position -= 30

    for obw in obwody:
        if y_position < 100:
            pdf_canvas.showPage()
            y_position = height - 50

        name = obw["nazwa"]
        el_count = _count_elements(name, elements)
        rcd = _assigned_rcd_label(name, rcd_groups)

        pdf_canvas.setFont("Helvetica-Bold", 10)
        pdf_canvas.drawString(50, y_position, f"Obwód: {name}")
        y_position -= 15
        pdf_canvas.setFont("Helvetica", 9)
        pdf_canvas.drawString(70, y_position, f"Zabezpieczenie: {obw['zabezpieczenie']}")
        y_position -= 12
        pdf_canvas.drawString(70, y_position, f"Przekrój: {obw['przekroj']}")
        y_position -= 12
        pdf_canvas.drawString(70, y_position, f"Długość: {obw['dlugosc']} m")
        y_position -= 12
        pdf_canvas.drawString(70, y_position, f"Liczba elementów: {el_count}")
        y_position -= 12
        pdf_canvas.drawString(70, y_position, f"RCD: {rcd}")
        y_position -= 20

    pdf_canvas.save()
    return raport_path


# -----------------------------------------
# Funkcja główna do generowania raportów
# -----------------------------------------
def generate_all_reports(obwody, elements, rcd_groups=None):
    _ensure_data_dir()

    txt_path = generate_txt(obwody, elements, rcd_groups)
    csv_path = generate_csv(obwody, elements, rcd_groups)
    pdf_path = generate_pdf(obwody, elements, rcd_groups) if REPORTLAB_AVAILABLE else None

    msg = f"Raporty zapisane:\n\nTXT: {txt_path}\nCSV: {csv_path}"
    if pdf_path:
        msg += f"\nPDF: {pdf_path}"
    else:
        msg += "\n(PDF pominięty – brak modułu reportlab)"
    print(msg)
    return msg
