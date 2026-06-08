# Route Animation Modules

Ten folder dzieli dawny duzy plik `05_pygame_route_animation.py` na mniejsze czesci.

- `app.py` - sklada caly proces: wybiera stacje, pobiera graf OSM, buduje trasy i uruchamia animacje.
- `cli.py` - argumenty terminala, np. `--station-count`, `--max-routes`, `--speed-kmh`, `--render-scale`.
- `config.py` - stale: sciezki do danych, rozmiar okna, kolory obszarow i skala UI.
- `models.py` - proste struktury `Station` i `RouteAnimation`.
- `data.py` - czyta `stations_df.parquet` i `edges_df.parquet`; wybiera top stacje z Twojej sieci.
- `osm_network.py` - obsluguje OSMnx i NetworkX; liczy najkrotsze trasy po drogach rowerowych.
- `geo.py` - przeliczenia wspolrzednych, odleglosci i dopasowanie mapy do okna.
- `cache.py` - tworzy nazwy plikow cache dla grafu OSM, tras i mapy.
- `basemap.py` - pobiera albo laduje szara mape CartoDB Positron.
- `animation.py` - silnik animacji: mapa, trasy, ruch rowerzystow.
- `ui.py` - interfejs `pygame`: menu, ekran ladowania, panele i przyciski.

Domyslnie animacja bierze `100` top stacji do wyznaczania tras i celuje w okno `2560 x 1440`, dopasowane do ekranu.
Statyczna warstwa mapy, tras i stacji jest renderowana w wyzszej jakosci (`--render-scale 1.35`) i wygladzana do rozmiaru okna.
Widok mapy ma niewielki margines wokol tras i stacji, z mniejszym odstepem u gory i na dole.
W lewym dolnym rogu mapy widoczna jest srednia trasa na mapie, czyli srednia z aktualnie widocznych tras, z podpisana podzialka co `0,5 km`.
W trybie 2-letnim wszystkie stacje sa widoczne na mapie jako delikatne tlo, a mocniej zaznaczone sa tylko stacje aktualnie pokazanych tras.
Stacje sa zaznaczone punktami albo wiekszymi klastrami w kolorach obszarow, ale bez podpisow, zeby mapa byla czytelniejsza.
Trasy pochodza z najczestszych polaczen stacja->stacja z danych (agregacja obu kierunkow), a geometria kazdej trasy jest liczona jako najkrotsza droga po OSM.
Po kazdej trasie jedzie dokladnie jeden rowerzysta.
Zeby mapa nie robila sie "spaghetti", domyslnie pokazywane jest maksymalnie `150` tras (najmocniejsze wedlug ruchu w sieci).
Gotowe geometrie tras sa zapisywane w cache, wiec kolejne uruchomienie jest lzejsze.
Legenda i statystyki sa w panelu po prawej stronie, poza mapa.
Panel pokazuje tez srednia trase na mapie, liczona z aktualnie widocznych tras po drogach OSM.
Kolor trasy i stacji oznacza przyblizony sektor Londynu: centrum oraz osiem kierunkow wokol centrum.

Glowny sposob uruchomienia zostaje bez zmian:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py
```

Po starcie zobaczysz menu w oknie `pygame` z wyborem trybu (klikalne przyciski):

- `1` - animacja na danych z 2 lat (2024-2025),
- `2` - porownanie: dni tygodnia i reczne przelaczanie na weekendy.

Po wyborze trybu to samo okno zostaje otwarte: pojawia sie ekran `Ladowanie...`, a potem od razu animacja.

Mozesz tez pominac menu i wybrac tryb argumentem:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode two_years
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode weekday_weekend
```

Jesli chcesz pokazac wiecej stacji w trybie 2-letnim, mozesz podac ich liczbe recznie:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --station-count 300
```

Mozesz tez recznie zmienic liczbe pokazywanych tras:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --max-routes 25
```

Jesli chcesz ostrzejsza mape i masz zapas pamieci, mozesz podniesc jakosc statycznej warstwy:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --render-scale 1.5
```

Domyslnie animacja jedzie teraz wolniej (`--time-scale 85`), a stacje poza aktywnymi trasami sa rysowane bardziej subtelnie.
W trybie dni tygodnia/weekendy wszystkie stacje sa widoczne jako delikatne tlo, a aktywne stacje aktualnego etapu sa mocniej podswietlone.
Porownanie wybiera po `100` top stacji dla dni tygodnia i weekendow i pokazuje maksymalnie `150` tras na etap.
Rozmiar plam stacji skaluje sie z czestotliwoscia odwiedzin dla aktualnego etapu.
W tym trybie po przelaczeniu etapu poprzedni zestaw tras zostaje delikatnie podswietlony w tle, zeby latwiej porownac przebiegi.

Sterowanie w oknie:

- `M` albo przycisk `Menu` - powrot do menu i wybor innej animacji.
- `TAB`/`T` albo przycisk `Pokaz weekendy / Pokaz dni tygodnia` - przelaczanie etapu w trybie dni tygodnia/weekendy.
- `Spacja` albo przycisk `Pauza` - pauza/wznowienie jazdy.
- `Esc` albo `Q` - zamkniecie animacji.
