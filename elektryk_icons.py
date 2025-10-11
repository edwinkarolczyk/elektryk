# elektryk_icons.py
# -----------------------------------------
# Moduł ikon i stylów wizualnych dla programu Domowy Elektryk
# -----------------------------------------

import os

ASSETS_DIR = 'assets'
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)

ICON_MAP = {
    'Gniazdko': '🔌',
    'Lampa': '💡',
    'Włącznik': '🔘',
    'Rozdzielnica': '🧰',
    'Czujnik': '📡',
    'Roleta': '🪟',
    'Pompa': '💧',
    'Bufor': '🪣',
}

def get_icon(typ):
    return ICON_MAP.get(typ, '⚙️')

def icon_label(typ):
    return f'{get_icon(typ)} {typ}'
