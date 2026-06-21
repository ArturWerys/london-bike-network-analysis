# Route Animation Modules

Ten folder dzieli dawny duzy plik `05_pygame_route_animation.py` na mniejsze czesci.

- `app.py` - sklada caly proces: wybiera stacje, pobiera graf OSM, buduje trasy i uruchamia animacje.
- `cli.py` - argumenty terminala, np. `--station-count`, `--max-routes`, `--speed-kmh`, `--render-scale`.
- `config.py` - stale: sciezki do danych, rozmiar okna, kolory obszarow i skala UI.
- `models.py` - proste struktury `Station` i `RouteAnimation`.
- `data.py` - czyta `stations_df.parquet` i dane bez nieciaglosci; wybiera top stacje z Twojej sieci.
- `osm_network.py` - obsluguje OSMnx i NetworkX; liczy najkrotsze trasy po drogach rowerowych.
- `geo.py` - przeliczenia wspolrzednych, odleglosci i dopasowanie mapy do okna.
- `cache.py` - tworzy nazwy plikow cache dla grafu OSM, tras i mapy.
- `basemap.py` - pobiera albo laduje szara mape CartoDB Positron.
- `animation.py` - silnik animacji: mapa, trasy, ruch rowerzystow.
- `ui.py` - interfejs `pygame`: menu, ekran ladowania, panele i przyciski.

Domyslnie dawna animacja bierze `100` top stacji, a tryb heatmapy `200` top stacji do wyznaczania tras i celuje w okno `2560 x 1440`, dopasowane do ekranu.
Wszystkie tryby animacji korzystaja z tego samego zakresu danych co analiza stopnia wezla: `Data/rides_data_without_discontinuities.parquet` po filtrze czasu `3-180 min`. Krawedzie do trybu 2-letniego sa cache'owane jako `Data/edges_without_discontinuities_3_180min.parquet`.
UI animacji korzysta z lokalnej czcionki Montserrat z katalogu `fonts/`, tak samo jak wykresy w notebookach.
Statyczna warstwa mapy, tras i stacji jest renderowana w wyzszej jakosci (`--render-scale 1.35`) i wygladzana do rozmiaru okna.
Widok mapy ma niewielki margines wokol tras i stacji, z mniejszym odstepem u gory i na dole.
W lewym dolnym rogu mapy widoczna jest srednia trasa na mapie, czyli srednia z aktualnie widocznych tras, z podpisana podzialka co `0,5 km`.
W trybie 2-letnim wszystkie stacje sa widoczne na mapie jako delikatne tlo, a mocniej zaznaczone sa tylko stacje aktualnie pokazanych tras.
Stacje sa zaznaczone osobnymi punktami bez klastrowania, ale bez podpisow, zeby mapa byla czytelniejsza.
Trasy pochodza z najczestszych polaczen stacja->stacja z danych (agregacja obu kierunkow), a geometria kazdej trasy jest liczona jako najkrotsza droga po OSM.
Po kazdej trasie jedzie dokladnie jeden rowerzysta.
Zeby mapa nie robila sie "spaghetti", dawna animacja pokazuje domyslnie maksymalnie `150` tras, a heatmapa do `300` najmocniejszych tras.
Gotowe geometrie tras sa zapisywane w cache, wiec kolejne uruchomienie jest lzejsze.
Legenda i statystyki sa w panelu po prawej stronie, poza mapa.
Na mapie widoczna jest tez srednia trasa, liczona z aktualnie widocznych tras po drogach OSM.
W dawnym trybie kolor trasy i stacji oznacza przyblizony sektor Londynu: centrum oraz osiem kierunkow wokol centrum.

Glowny sposob uruchomienia zostaje bez zmian:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py
```

Po starcie zobaczysz menu w oknie `pygame` z wyborem trybu (klikalne przyciski):

- `1` - animacja dwóch lat, gdzie kolory pokazuja natężenie przejazdow i waznosc stacji,
- `2` - podmenu `Dawne tryby`, z poprzednia animacja przejazdow z pelnego okresu 2 lat.

W trybie `Animacja dwóch lat` zakres danych wybierasz w panelu po prawej stronie:
pełne 2 lata, dni tygodnia albo weekendy.

Po wyborze trybu to samo okno zostaje otwarte: pojawia sie ekran `Ladowanie...`, a potem od razu animacja.

Mozesz tez pominac menu i wybrac tryb argumentem:

```powershell
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode two_years
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode two_years_heatmap
.\.venv\Scripts\python.exe .\05_pygame_route_animation.py --mode weekday_weekend
```

W menu glownym `two_years_heatmap` jest pokazywany jako `Animacja dwóch lat`, a stary `two_years` zostaje w podmenu `Dawne tryby`. `weekday_weekend` dziala jako alias do wspolnego trybu heatmapy.

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
Predkosc rowerzystow domyslnie wynosi `10 km/h` i jest liczona po rzeczywistej dlugosci trasy OSM miedzy stacjami, niezaleznie od odleglosci w pikselach.
W heatmapie wszystkie stacje sa widoczne jako delikatne tlo, a aktywne stacje aktualnego zakresu sa mocniej podswietlone.
Zakres danych w panelu po prawej stronie przelacza pelne 2 lata, dni tygodnia albo weekendy; kazdy zakres ma wlasne wagi, kolory i prog filtra.
Tryb animacji dwóch lat wybiera top relacje miedzy parami stacji z puli `200` najwazniejszych stacji, a domyslnie pokazuje do `300` tras dla kazdego zakresu.
Kolory tras i rowerzystow skaluja sie wedlug lacznej liczby przejazdow w obu kierunkach.
Kolory wezlow wynikaja z sumy przejazdow wchodzacych i wychodzacych, a rowerzysci jada w tym kierunku, ktory byl czestszy dla danej pary stacji.
Paleta heatmapy idzie od niebieskiego dla nizszych wartosci do czerwonego dla najwyzszych wartosci.
Polaczenia tras w trybie heatmapy sa rysowane stala, wyrazna gruboscia i z wyzsza nieprzezroczystoscia, zeby skala kolorow byla czytelniejsza.
Rowerzysci sa rysowani mniejszymi punktami, zeby przy gestych trasach nie zaslaniali mapy.

Sterowanie w oknie:

- `M` albo przycisk `Menu` - powrot do menu i wybor innej animacji.
- `TAB`/`T` albo segment `2 lata / Dni tyg. / Weekendy` w prawym panelu - zmiana zakresu danych heatmapy.
- Suwak progu w prawym panelu - filtrowanie tras wedlug lacznej liczby przejazdow; liczba rowerzystow wynika z liczby tras po filtrze. Zakres suwaka dopasowuje sie do aktywnych danych, a pozycja suwaka zostaje zachowana po zmianie zakresu.
- `Spacja` albo przycisk `Pauza` - pauza/wznowienie jazdy.
- `Esc` albo `Q` - zamkniecie animacji.
