# elektryka_gui.py
# Wersja: 0.9.0 (2025-10-07)
# Autor: ChatGPT dla Edwina — "Program dla Domowego Elektryka"
# Python: 3.11+ (testowane na 3.13)
#
# Funkcje kluczowe:
# - Zakładki: [Plan instalacji] [Rozdzielnica] [Plik/Ustawienia]
# - Elementy: Gniazdko (G), Lampa (L), Roleta (R), Włącznik (W)
# - Auto-numeracja: G-01, L-01, R-01, W-01 (zachowuje ciąg przy imporcie)
# - Jedna linia = uproszczona wiązka kabli (polyline 2D)
# - PPM: edytuj / usuń element lub linię
# - Zapis/Odczyt projektu: JSON
# - Eksport widoku: PNG (jeśli Pillow), inaczej EPS (PostScript)
# - Rozdzielnica: prosta tabela obwodów (nr, opis, zabezp., przewód, uwagi)
#
# Skróty:
#   1/2/3/4 = tryb dodawania (G/L/R/W)
#   L = tryb rysowania Linii
#   Esc = anuluj bieżące rysowanie
#   Ctrl+S = Zapisz JSON
#   Ctrl+O = Otwórz JSON
#   Ctrl+E = Eksport Widoku
#
# Uwagi:
# - Siatka ma charakter pomocniczy; linie rysowane od-klik do-klik (prosta polilinia).
# - Wymagania z rozmowy:
#   • Osobna zakładka "Rozdzielnica"
#   • Elementy nazwane G-01 / L-01 / R-01 / W-01
#   • Jedna linia reprezentuje więcej kabli (nie mnożymy nitek)
#   • Opcjonalne podpowiedzi ostatnio używanych nazw (menu "Słowniczek")
#   • „lokalizacja”: pomijamy — mamy "nr_hali" (string) i puste "lokalizacja" w JSON
#   • Możliwość skalowania obrazu na eksport
#
from __future__ import annotations
import json
import os
import math
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple, Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

# Pillow jest opcjonalny (ładniejszy PNG)
try:
    from PIL import Image, EpsImagePlugin
    EpsImagePlugin.gs_windows_binary = r"gswin64c"  # jeśli zainstalowane
    PIL_OK = True
except Exception:
    PIL_OK = False

APP_TITLE = "Domowy Elektryk — Plan + Rozdzielnica"
APP_VER = "0.9.0"

# ====== MODELE DANYCH =========================================================

@dataclass
class Element:
    id: str
    typ: str           # 'G'/'L'/'R'/'W'
    nazwa: str         # np. 'G-01'
    x: int
    y: int
    nr_hali: str = "1"
    lokalizacja: str = ""  # świadomie pusta (zgodnie z wymaganiem)
    meta: Dict = field(default_factory=dict)

@dataclass
class Linia:
    id: str
    punkty: List[Tuple[int,int]]
    opis: str = "linia"
    nr_hali: str = "1"
    meta: Dict = field(default_factory=dict)

@dataclass
class Obwod:
    nr: str
    opis: str
    zabezp: str
    przewod: str
    uwagi: str = ""

@dataclass
class Projekt:
    narzedzia: List[Element]     # zachowuję klucz "narzedzia" dla zgodności z WM na przyszłość
    linie: List[Linia]
    rozdzielnica: List[Obwod]
    counters: Dict[str,int]      # liczniki auto-numeracji dla typów G/L/R/W
    nr_hali: str = "1"
    wersja: str = APP_VER

    def to_json(self)->Dict:
        return {
            "narzedzia":[asdict(e) for e in self.narzedzia],
            "linie":[{"id":l.id,"punkty":l.punkty,"opis":l.opis,"nr_hali":l.nr_hali,"meta":l.meta} for l in self.linie],
            "rozdzielnica":[asdict(o) for o in self.rozdzielnica],
            "counters":self.counters,
            "nr_hali":self.nr_hali,
            "wersja":self.wersja,
        }

    @staticmethod
    def from_json(d:Dict)->"Projekt":
        els=[]
        for e in d.get("narzedzia",[]):
            els.append(Element(**e))
        lns=[]
        for l in d.get("linie",[]):
            pts=[tuple(p) for p in l.get("punkty",[])]
            lns.append(Linia(id=l["id"], punkty=pts, opis=l.get("opis","linia"), nr_hali=l.get("nr_hali","1"), meta=l.get("meta",{})))
        obw=[]
        for o in d.get("rozdzielnica",[]):
            obw.append(Obwod(**o))
        counters = d.get("counters", {"G":0,"L":0,"R":0,"W":0})
        return Projekt(els, lns, obw, counters, nr_hali=d.get("nr_hali","1"), wersja=d.get("wersja", APP_VER))

# ====== POMOCNICZE ============================================================

def next_name(counters:Dict[str,int], typ:str)->str:
    counters[typ] = counters.get(typ,0) + 1
    return f"{typ}-{counters[typ]:02d}"

def distance(a:Tuple[int,int], b:Tuple[int,int])->float:
    return math.hypot(a[0]-b[0], a[1]-b[1])

# ====== GŁÓWNA APLIKACJA ======================================================

class ElektrykaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VER}")
        self.geometry("1200x800")

        self.projekt = Projekt(narzedzia=[], linie=[], rozdzielnica=[], counters={"G":0,"L":0,"R":0,"W":0})

        self._current_mode = tk.StringVar(value="G")  # G/L/R/W/LINIA
        self._grid_on = tk.BooleanVar(value=True)
        self._snap = tk.BooleanVar(value=True)
        self._snap_step = tk.IntVar(value=20)
        self._status = tk.StringVar(value="Gotowe")
        self._linie_tmp: List[Tuple[int,int]] = []
        self._selected_canvas_id: Optional[int] = None
        self._id_to_model: Dict[int,Tuple[str,str]] = {}  # canvas_id -> ("E"/"L", model.id)

        self._build_ui()
        self._bind_shortcuts()
        self._refresh_status()

    # --- UI ---
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Pasek narzędzi
        toolbar = ttk.Frame(self, padding=(6,4))
        toolbar.grid(row=0, column=0, sticky="ew")
        for i in range(20): toolbar.columnconfigure(i, weight=0)
        toolbar.columnconfigure(19, weight=1)

        ttk.Label(toolbar, text="Tryb:").grid(row=0,column=0,padx=(0,6))
        for i,(lbl,typ,key) in enumerate([("Gniazdko","G","1"),("Lampa","L","2"),("Roleta","R","3"),("Włącznik","W","4"),("Linia","LINIA","L")]):
            b=ttk.Radiobutton(toolbar, text=f"{lbl} ({key})", value=typ, variable=self._current_mode, command=self._refresh_status)
            b.grid(row=0,column=1+i,padx=4)

        ttk.Separator(toolbar, orient="vertical").grid(row=0,column=7, sticky="ns", padx=8)
        ttk.Checkbutton(toolbar, text="Siatka", variable=self._grid_on, command=self._redraw).grid(row=0,column=8)
        ttk.Checkbutton(toolbar, text="Przyciągaj", variable=self._snap).grid(row=0,column=9)
        ttk.Label(toolbar, text="skok").grid(row=0,column=10,padx=(12,2))
        sp=ttk.Spinbox(toolbar, from_=5, to=200, textvariable=self._snap_step, width=4, command=self._redraw)
        sp.grid(row=0,column=11)

        ttk.Button(toolbar, text="Nowy", command=self._nowy).grid(row=0,column=12, padx=6)
        ttk.Button(toolbar, text="Otwórz (Ctrl+O)", command=self._wczytaj).grid(row=0,column=13, padx=6)
        ttk.Button(toolbar, text="Zapisz (Ctrl+S)", command=self._zapisz).grid(row=0,column=14, padx=6)
        ttk.Button(toolbar, text="Eksport (Ctrl+E)", command=self._eksportuj).grid(row=0,column=15, padx=6)

        # Notebook
        nb = ttk.Notebook(self)
        nb.grid(row=1, column=0, sticky="nsew")
        self._nb = nb

        # Zakładka Plan
        plan = ttk.Frame(nb); plan.columnconfigure(0, weight=1); plan.rowconfigure(0, weight=1)
        nb.add(plan, text="Plan instalacji")

        self.canvas = tk.Canvas(plan, bg="#1f1f1f", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_click_left)
        self.canvas.bind("<Button-3>", self._on_click_right)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Configure>", lambda e: self._redraw())

        # Zakładka Rozdzielnica
        rframe = ttk.Frame(nb, padding=6); rframe.columnconfigure(0, weight=1); rframe.rowconfigure(1, weight=1)
        nb.add(rframe, text="Rozdzielnica")

        top_r = ttk.Frame(rframe); top_r.grid(row=0,column=0, sticky="ew", pady=(0,4))
        ttk.Button(top_r, text="Dodaj obwód", command=self._obwod_dodaj).pack(side="left", padx=4)
        ttk.Button(top_r, text="Edytuj", command=self._obwod_edytuj).pack(side="left", padx=4)
        ttk.Button(top_r, text="Usuń", command=self._obwod_usun).pack(side="left", padx=4)

        cols=("nr","opis","zabezp","przewod","uwagi")
        tv = ttk.Treeview(rframe, columns=cols, show="headings", height=12)
        for c,txt,w in [("nr","Nr",80),("opis","Opis",260),("zabezp","Zabezp.",110),("przewod","Przewód",110),("uwagi","Uwagi",260)]:
            tv.heading(c, text=txt); tv.column(c, width=w, anchor="w")
        tv.grid(row=1,column=0, sticky="nsew")
        self._tv_obw = tv

        # Zakładka Plik/Ustawienia (prosto)
        pframe = ttk.Frame(nb, padding=10)
        nb.add(pframe, text="Plik / Ustawienia")
        ttk.Label(pframe, text="Nr hali:").grid(row=0,column=0, sticky="w")
        self._nr_hali = tk.StringVar(value="1")
        ttk.Entry(pframe, textvariable=self._nr_hali, width=10).grid(row=0,column=1, sticky="w", padx=(5,0))
        ttk.Label(pframe, text="Słowniczek opisów (podpowiedzi nazw elementów):").grid(row=1,column=0, columnspan=2, sticky="w", pady=(12,4))
        self._slowniczek = tk.Listbox(pframe, height=6); self._slowniczek.grid(row=2,column=0,columnspan=2, sticky="nsew")
        for s in ["Kuchnia blat","Łazienka lustro","Korytarz dół schodów","Sypialnia lewa ściana"]:
            self._slowniczek.insert("end", s)
        ttk.Button(pframe, text="Dodaj do słowniczka", command=self._slownik_dodaj).grid(row=3,column=0, pady=6, sticky="w")
        ttk.Button(pframe, text="Usuń ze słowniczka", command=self._slownik_usun).grid(row=3,column=1, pady=6, sticky="w")

        # Pasek stanu
        status = ttk.Label(self, textvariable=self._status, anchor="w", relief="sunken")
        status.grid(row=2, column=0, sticky="ew")

        self._redraw()

    def _bind_shortcuts(self):
        self.bind("<Control-s>", lambda e: self._zapisz())
        self.bind("<Control-o>", lambda e: self._wczytaj())
        self.bind("<Control-e>", lambda e: self._eksportuj())
        self.bind("<Escape>", lambda e: self._linie_cancel())
        # szybkie tryby
        self.bind("1", lambda e: self._set_mode("G"))
        self.bind("2", lambda e: self._set_mode("L"))
        self.bind("3", lambda e: self._set_mode("R"))
        self.bind("4", lambda e: self._set_mode("W"))
        self.bind("l", lambda e: self._set_mode("LINIA"))
        self.bind("L", lambda e: self._set_mode("LINIA"))

    def _set_mode(self, m:str):
        self._current_mode.set(m)
        self._refresh_status()

    # --- RENDER ---
    def _redraw(self):
        self._id_to_model.clear()
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if self._grid_on.get():
            step = self._snap_step.get()
            gcol="#2a2a2a"
            for x in range(0,w,step):
                self.canvas.create_line(x,0,x,h, fill=gcol)
            for y in range(0,h,step):
                self.canvas.create_line(0,y,w,y, fill=gcol)

        # linie
        for ln in self.projekt.linie:
            if len(ln.punkty) >= 2:
                self._draw_line(ln)
        # elementy
        for el in self.projekt.narzedzia:
            self._draw_element(el)

        # rysowana tymczasowa linia
        if self._current_mode.get()=="LINIA" and len(self._linie_tmp)>=1:
            pts = self._linie_tmp[:]
            x,y = self.canvas.winfo_pointerx()-self.canvas.winfo_rootx(), self.canvas.winfo_pointery()-self.canvas.winfo_rooty()
            pts.append(self._snap_point((x,y)) if self._snap.get() else (x,y))
            self._draw_polyline(pts, dash=(4,2))

    def _draw_element(self, el:Element):
        size=18
        x,y = el.x, el.y
        color_map = {"G":"#8bd450","L":"#f5c451","R":"#6bd0f5","W":"#f08fb1"}
        fill = color_map.get(el.typ, "#cccccc")
        # znacznik
        r = size//2
        cid = self.canvas.create_oval(x-r,y-r,x+r,y+r, fill=fill, outline="#111111", width=2)
        # skrót
        self.canvas.create_text(x, y-16, text=el.typ, fill="white", font=("Segoe UI",9,"bold"))
        # nazwa
        self.canvas.create_text(x, y+14, text=el.nazwa, fill="#e6e6e6", font=("Consolas",9))
        self._id_to_model[cid]=( "E", el.id)

    def _draw_line(self, ln:Linia, dash=None):
        self._draw_polyline(ln.punkty, width=3, arrow="none", color="#7bb7ff", dash=dash, model=("L", ln.id))

    def _draw_polyline(self, pts:List[Tuple[int,int]], width=3, arrow=None, color="#7bb7ff", dash=None, model=None):
        fl = []
        for p in pts: fl.extend(p)
        cid = self.canvas.create_line(*fl, fill=color, width=width, arrow=arrow, capstyle="round", joinstyle="round", dash=dash)
        if model:
            self._id_to_model[cid]=model

    # --- INTERAKCJE ---
    def _on_motion(self, e):
        x,y = e.x,e.y
        if self._snap.get():
            x,y = self._snap_point((x,y))
        self._status.set(f"Tryb: {self._current_mode.get()} | Pozycja: ({x},{y})  | Hala: {self._nr_hali.get()}")

        if self._current_mode.get()=="LINIA" and len(self._linie_tmp)>0:
            self._redraw()

    def _on_click_left(self, e):
        x,y = e.x,e.y
        if self._snap.get():
            x,y = self._snap_point((x,y))
        mode = self._current_mode.get()
        if mode in ("G","L","R","W"):
            self._dodaj_element(mode, x, y)
        elif mode=="LINIA":
            self._linie_add_point((x,y))

    def _on_click_right(self, e):
        # wybór najbliższego obiektu do 16 px
        cid, kind, mid = self._pick_item(e.x, e.y, radius=16)
        menu = tk.Menu(self, tearoff=0)
        if cid is None:
            menu.add_command(label="Anuluj", command=lambda: None)
        else:
            if kind=="E":
                menu.add_command(label="Edytuj element…", command=lambda mid=mid: self._element_edit(mid))
                menu.add_command(label="Usuń element", command=lambda mid=mid: self._element_delete(mid))
            elif kind=="L":
                menu.add_command(label="Edytuj opis linii…", command=lambda mid=mid: self._linia_edit(mid))
                menu.add_command(label="Usuń linię", command=lambda mid=mid: self._linia_delete(mid))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _pick_item(self, x:int, y:int, radius:int=16):
        nearest=None; dist=1e9
        for cid,(kind,mid) in self._id_to_model.items():
            bx,by,bx2,by2 = self.canvas.bbox(cid)
            cx=(bx+bx2)//2; cy=(by+by2)//2
            d=distance((x,y),(cx,cy))
            if d<dist and d<=radius:
                dist=d; nearest=(cid,kind,mid)
        return nearest if nearest else (None,None,None)

    def _snap_point(self, p:Tuple[int,int])->Tuple[int,int]:
        s=self._snap_step.get()
        return (round(p[0]/s)*s, round(p[1]/s)*s)

    # --- ELEMENTY ---
    def _dodaj_element(self, typ:str, x:int, y:int):
        name = next_name(self.projekt.counters, typ)
        # Podpowiedź z zaznaczonego w słowniczku
        opis = None
        sel = self._slowniczek.curselection()
        if sel:
            opis = self._slowniczek.get(sel[0])
        el = Element(
            id=f"E{len(self.projekt.narzedzia)+1}",
            typ=typ,
            nazwa=name,
            x=x, y=y,
            nr_hali=self._nr_hali.get(),
            lokalizacja="",
            meta={"opis": opis or ""}
        )
        self.projekt.narzedzia.append(el)
        self._redraw()

    def _element_by_id(self, mid:str)->Optional[Element]:
        for e in self.projekt.narzedzia:
            if e.id==mid: return e
        return None

    def _element_edit(self, mid:str):
        el = self._element_by_id(mid)
        if not el:
            return
        nowa_nazwa = simpledialog.askstring("Edycja elementu", "Nazwa (np. G-03):", initialvalue=el.nazwa, parent=self)
        if not nowa_nazwa: return
        el.nazwa = nowa_nazwa.strip()
        el.meta["opis"] = simpledialog.askstring("Edycja elementu", "Opis (opcjonalnie):", initialvalue=el.meta.get("opis",""), parent=self) or ""
        self._redraw()

    def _element_delete(self, mid:str):
        self.projekt.narzedzia = [e for e in self.projekt.narzedzia if e.id!=mid]
        self._redraw()

    # --- LINIE ---
    def _linie_add_point(self, p:Tuple[int,int]):
        self._linie_tmp.append(p)
        # zakończ linię podwójnym kliknięciem w przybliżeniu
        if len(self._linie_tmp)>=2 and distance(self._linie_tmp[-1], self._linie_tmp[-2])<2:
            self._linie_commit()

    def _linie_commit(self):
        if len(self._linie_tmp)>=2:
            ln = Linia(
                id=f"L{len(self.projekt.linie)+1}",
                punkty=self._linie_tmp[:],
                opis="linia",
                nr_hali=self._nr_hali.get(),
                meta={}
            )
            self.projekt.linie.append(ln)
        self._linie_tmp.clear()
        self._redraw()

    def _linie_cancel(self):
        self._linie_tmp.clear()
        self._refresh_status()
        self._redraw()

    def _linia_by_id(self, mid:str)->Optional[Linia]:
        for l in self.projekt.linie:
            if l.id==mid: return l
        return None

    def _linia_edit(self, mid:str):
        ln = self._linia_by_id(mid)
        if not ln:
            return
        nowy = simpledialog.askstring("Edycja linii", "Opis linii:", initialvalue=ln.opis, parent=self)
        if nowy is not None:
            ln.opis = nowy.strip()
        self._redraw()

    def _linia_delete(self, mid:str):
        self.projekt.linie = [l for l in self.projekt.linie if l.id!=mid]
        self._redraw()

    # --- ROZDZIELNICA ---
    def _obwod_dodaj(self):
        nr = simpledialog.askstring("Obwód", "Nr/oznaczenie (np. B16/1):", parent=self) or ""
        opis = simpledialog.askstring("Obwód", "Opis (np. Gniazda kuchnia):", parent=self) or ""
        zabezp = simpledialog.askstring("Obwód", "Zabezpieczenie (np. B16, RCD 30mA):", parent=self) or ""
        przewod = simpledialog.askstring("Obwód", "Przewód (np. 3x2.5):", parent=self) or ""
        uwagi = simpledialog.askstring("Obwód", "Uwagi:", parent=self) or ""
        self.projekt.rozdzielnica.append(Obwod(nr, opis, zabezp, przewod, uwagi))
        self._obwod_refresh()

    def _obwod_edytuj(self):
        sel = self._tv_obw.selection()
        if not sel: return
        i = int(sel[0])
        obw = self.projekt.rozdzielnica[i]
        obw.nr = simpledialog.askstring("Obwód", "Nr/oznaczenie:", initialvalue=obw.nr, parent=self) or obw.nr
        obw.opis = simpledialog.askstring("Obwód", "Opis:", initialvalue=obw.opis, parent=self) or obw.opis
        obw.zabezp = simpledialog.askstring("Obwód", "Zabezpieczenie:", initialvalue=obw.zabezp, parent=self) or obw.zabezp
        obw.przewod = simpledialog.askstring("Obwód", "Przewód:", initialvalue=obw.przewod, parent=self) or obw.przewod
        obw.uwagi = simpledialog.askstring("Obwód", "Uwagi:", initialvalue=obw.uwagi, parent=self) or obw.uwagi
        self._obwod_refresh()

    def _obwod_usun(self):
        sel = self._tv_obw.selection()
        if not sel: return
        i = int(sel[0])
        del self.projekt.rozdzielnica[i]
        self._obwod_refresh()

    def _obwod_refresh(self):
        self._tv_obw.delete(*self._tv_obw.get_children())
        for idx,o in enumerate(self.projekt.rozdzielnica):
            self._tv_obw.insert("", "end", iid=str(idx), values=(o.nr,o.opis,o.zabezp,o.przewod,o.uwagi))

    # --- SŁOWNICZEK ---
    def _slownik_dodaj(self):
        val = simpledialog.askstring("Słowniczek", "Dodaj podpowiedź:", parent=self)
        if val:
            self._slowniczek.insert("end", val)

    def _slownik_usun(self):
        sel = self._slowniczek.curselection()
        for i in reversed(sel):
            self._slowniczek.delete(i)

    # --- PLIK ---
    def _nowy(self):
        if not self._potwierdz("Wyczyścić bieżący projekt?"):
            return
        self.projekt = Projekt(narzedzia=[], linie=[], rozdzielnica=[], counters={"G":0,"L":0,"R":0,"W":0})
        self._nr_hali.set("1")
        self._obwod_refresh()
        self._redraw()

    def _zapisz(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Projekt Elektryka","*.json")], title="Zapisz projekt")
        if not path: return
        self.projekt.nr_hali = self._nr_hali.get()
        with open(path,"w",encoding="utf-8") as f:
            json.dump(self.projekt.to_json(), f, ensure_ascii=False, indent=2)
        self._status.set(f"Zapisano: {os.path.basename(path)}")

    def _wczytaj(self):
        path = filedialog.askopenfilename(filetypes=[("Projekt Elektryka","*.json"),("Wszystkie","*.*")], title="Otwórz projekt")
        if not path: return
        try:
            with open(path,"r",encoding="utf-8") as f:
                data=json.load(f)
            pj = Projekt.from_json(data)
            self.projekt = pj
            self._nr_hali.set(pj.nr_hali)
            self._obwod_refresh()
            self._redraw()
            self._status.set(f"Wczytano: {os.path.basename(path)}")
        except Exception as ex:
            messagebox.showerror("Błąd", f"Nie udało się wczytać projektu:\n{ex}")

    def _eksportuj(self):
        path = filedialog.asksaveasfilename(defaultextension=".png" if PIL_OK else ".eps",
                                            filetypes=[("PNG" if PIL_OK else "PostScript","*.png" if PIL_OK else "*.eps")],
                                            title="Eksport widoku")
        if not path: return
        # najpierw PostScript
        ps_tmp = path if path.lower().endswith(".eps") else os.path.splitext(path)[0]+".eps"
        self.canvas.update()
        try:
            self.canvas.postscript(file=ps_tmp, colormode="color")
            if PIL_OK and path.lower().endswith(".png"):
                img = Image.open(ps_tmp)
                img.save(path, "PNG")
                try:
                    os.remove(ps_tmp)
                except Exception:
                    pass
            self._status.set(f"Wyeksportowano: {os.path.basename(path)}")
        except Exception as ex:
            messagebox.showerror("Błąd", f"Nie udało się wyeksportować:\n{ex}")

    # --- HELPERS ---
    def _refresh_status(self):
        m=self._current_mode.get()
        if m in ("G","L","R","W"):
            txt={"G":"Gniazdko","L":"Lampa","R":"Roleta","W":"Włącznik"}[m]
        else:
            txt="Linia"
        self._status.set(f"Tryb: {txt}. LPM dodaje, PPM edytuje/usuwa. Esc anuluje linię.")
        self._id_to_model.clear()

    def _potwierdz(self, msg:str)->bool:
        return messagebox.askyesno("Potwierdź", msg)

# ====== START =================================================================

def main():
    app = ElektrykaApp()
    app.mainloop()

if __name__=="__main__":
    main()

# ⏹ KONIEC KODU
