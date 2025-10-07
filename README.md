# Elektryka

`Elektryka` to lekka aplikacja desktopowa oparta o Tkinter, służąca do
planowania prostych instalacji elektrycznych. Pozwala na tworzenie projektu
wielodomowego i wielopokojowego, rysowanie elementów na rzutach pomieszczeń,
przypisywanie kabli, obliczanie obciążeń i spadków napięć oraz eksport
raportu do formatu PDF.

## Jak uruchomić

1. Zainstaluj Python w wersji 3.11 lub nowszej.
2. Opcjonalnie zainstaluj Pillow oraz reportlab, aby móc korzystać z
   wczytywania obrazów i eksportu PDF:
   ```bash
   pip install pillow reportlab
   ```
3. W wierszu poleceń przejdź do katalogu `elektryka_full` i uruchom:
   ```bash
   python elektryka.py
   ```
4. Na platformie Windows możesz użyć pliku `Start_Elektryka.bat`.

## Funkcje

- **Wiele domów i pokoi** – twórz strukturę projektu zgodną z rzeczywistym
  budynkiem. Lista domów i pokoi znajduje się w lewym panelu. 
- **Tła w formacie JPG/JPEG/PNG** – dla każdego pokoju można wczytać rzut
  pomieszczenia jako obraz tła (menu Plik → Wczytaj projekt lub w edycji
  pokoju). Obraz zostaje dopasowany proporcjonalnie do canvasu.
- **Rysowanie elementów** – kliknięcie w płótno otwiera okno dodawania
  elementu, w którym podajesz typ (gniazdko, włącznik, lampa, roleta),
  wariant, kategorię obwodu, etykietę oraz listę połączeń (kabli). W
  edycji możesz dodać wiele połączeń z różnymi kablami i żyłami.
- **Kable i żyły** – obsługiwane są typy kabli: 2×1.5, 3×1.5, 3×2.5,
  5×2.5, 5×4, 5×6, 5×10. Dla każdego kabla domyślnie ustawione są żyły
  (L, N, PE, L1, L2, L3) zgodnie z normami. Możesz włączać/wyłączać żyły
  oraz uzupełnić długość przewodu i moc odbiornika.
- **Rozdzielnica** – każdy przewód, którego zaznaczono opcję „do rozdz.”,
  trafia do listy „wolnych przewodów”. W menedżerze obwodów (menu
  `Obwody`) można tworzyć obwody, ustawiać zabezpieczenie (B/C/D), RCD,
  kategorię i kolor. Przewody z listy wolnych można przypisywać do
  obwodów. Program sugeruje przekroje i obciążenia.
- **Obliczenia** – aplikacja oblicza spadek napięcia i procentowy
  obciążenie obwodu. Kolor żółty sygnalizuje zbliżanie się do limitu, a
  czerwony przekroczenie normy.
- **Eksport PDF** – wygeneruj raport z rzutami poszczególnych pomieszczeń,
  tabelą połączeń (dla każdego elementu: kabel, spadek napięcia, status)
  oraz zestawieniem obwodów (ID, nazwa, kategoria, zabezpieczenie, RCD,
  obciążenie). Do eksportu potrzebne są biblioteki Pillow i reportlab.
- **Ustawienia** – wszystkie parametry programu, takie jak kolory żył,
  obsługiwane kable, limity spadków napięcia, domyślne moce
  poszczególnych elementów itp. znajdują się w pliku `settings.json`. Można
  tam wprowadzać zmiany bez modyfikacji kodu.

## Pliki

- `elektryka.py` – główny plik źródłowy z aplikacją Tkinter.
- `settings.json` – ustawienia konfiguracyjne (typy kabli, kolory, limity).
- `Start_Elektryka.bat` – plik uruchomieniowy dla Windows.

## Licencja

Projekt jest dostarczany „as is”, bez gwarancji. Swobodnie modyfikuj i
rozbudowuj go na własny użytek.

# Elektryka — Full Upgrade (0.6.0)

Nowości:
- Tło **dla każdego pokoju** (JPG/JPEG/PNG) — wczytywanie i czyszczenie z lewego panelu.
- Pokazywanie **tylko wybranego obwodu** (filtr) + przełącznik **pasków żył**.
- W oknie **Połączenia** możesz przypisać **obwód** bezpośrednio do połączenia (`circuit_id`).
- **Edytor elementu** (PPM → „Edytuj element…”) pozwala:
  - ustawić **etykietę**, **moc [W]**,
  - nadać **max prąd [A]** (gniazdka domyślnie 16A → ~3680W),
  - **połączyć szeregowo** z innym elementem tego samego typu (wybór „Ciąg dalszy z…”).
- PDF wyświetla te same etykiety (~W, A).

Uruchomienie:
1. `pip install pillow`
2. `python elektryka.py` (Windows: `Start_Elektryka.bat`)
