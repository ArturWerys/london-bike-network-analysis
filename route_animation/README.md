# Route Animation Modules

Ten folder dzieli dawny duzy plik `05_pygame_route_animation.py` na mniejsze czesci.

- `app.py` - sklada caly proces: wybiera stacje, pobiera graf OSM, buduje trasy i uruchamia animacje.
- `cli.py` - argumenty terminala, np. `--station-count`, `--route-length`, `--speed-kmh`.
- `config.py` - stale: sciezki do danych, rozmiar okna, kolory obszarow i liczba rowerzystow.
- `models.py` - proste struktury `Station` i `RouteAnimation`.
- `data.py` - czyta `stations_df.parquet` i `edges_df.parquet`; wybiera top stacje z Twojej sieci.
- `osm_network.py` - obsluguje OSMnx i NetworkX; liczy najkrotsze trasy po drogach rowerowych.
- `geo.py` - przeliczenia wspolrzednych, odleglosci i dopasowanie mapy do okna.
- `cache.py` - tworzy nazwy plikow cache dla grafu OSM, tras i mapy.
- `basemap.py` - pobiera albo laduje szara mape CartoDB Positron.
- `animation.py` - silnik animacji: mapa, trasy, ruch rowerzystow.
- `ui.py` - interfejs `pygame`: menu, ekran ladowania, panele i przyciski.

Domyslnie animacja bierze wszystkie `801` stacji z danych i otwiera okno `1920 x 1080`.
Stacje sa zaznaczone punktami albo wiekszymi klastrami, ale bez podpisow, zeby mapa byla czytelniejsza.
Trasy pochodza z najczestszych polaczen stacja->stacja z danych (agregacja obu kierunkow), a geometria kazdej trasy jest liczona jako najkrotsza droga po OSM.
Po kazdej trasie jedzie dokladnie jeden rowerzysta.
Zeby mapa nie robila sie "spaghetti", domyslnie pokazywane jest maksymalnie `35` tras (najmocniejsze wedlug ruchu w sieci).
Gotowe geometrie tras sa zapisywane w cache, wiec kolejne uruchomienie jest lzejsze.
Legenda i statystyki sa w panelu po prawej stronie, poza mapa.
Kolor trasy oznacza przyblizony obszar Londynu: centrum, polnoc, wschod, poludnie albo zachod.

Glowny sposob uruchomienia zostaje bez zmian:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py
```

Po starcie zobaczysz menu w oknie `pygame` z wyborem trybu (klikalne przyciski):

- `1` - animacja na danych z 2 lat (2024-2025),
- `2` - porownanie: dni robocze i reczne przelaczanie na weekend.

Po wyborze trybu to samo okno zostaje otwarte: pojawia sie ekran `Ladowanie...`, a potem od razu animacja.

Mozesz tez pominac menu i wybrac tryb argumentem:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode two_years
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode weekday_weekend
```

Jesli komputer ma problem z pelna wersja 2-letnia, mozna tymczasowo odpalic lzejszy wariant:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --station-count 300
```

Mozesz tez recznie zmienic liczbe pokazywanych tras:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --max-routes 25
```

Domyslnie animacja jedzie teraz wolniej (`--time-scale 85`), a stacje poza aktywnymi trasami sa rysowane bardziej subtelnie.
W trybie weekday/weekend rozmiar plam stacji skaluje sie z czestotliwoscia odwiedzin dla aktualnego etapu.
W tym trybie po przelaczeniu etapu poprzedni zestaw tras zostaje delikatnie podswietlony w tle, zeby latwiej porownac przebiegi.

Sterowanie w oknie:

- `M` albo przycisk `Menu` - powrot do menu i wybor innej animacji.
- `TAB`/`T` albo przycisk `Pokaz weekend / Pokaz weekday` - przelaczanie etapu w trybie weekday/weekend.
- `Spacja` albo przycisk `Pauza` - pauza/wznowienie jazdy.
- `Esc` albo `Q` - zamkniecie animacji.
