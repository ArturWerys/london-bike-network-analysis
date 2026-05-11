from pathlib import Path
import pandas as pd
import xml.etree.ElementTree as ET

# ---------- Goal ----------
# The goal of this script is to load and combine the trip data from 2024 and 2025.
# This data will be used for stohastic project. 
# Coded by: Artur Werys


# ---------- Paths ----------

BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "Data"

DATA_2024_DIR = DATA_DIR / "2024"
DATA_2025_DIR = DATA_DIR / "2025"

STATIONS_FILE = DATA_DIR / "stations.xml"


# ---------- Function for loading CSV data ----------

def load_data(folder_path):
    files = list(folder_path.glob("*.csv"))
    dataframes = []

    for file in files:
        df = pd.read_csv(file)
        dataframes.append(df)

    combined_data = pd.concat(dataframes, ignore_index=True)

    return combined_data


# ---------- Loading data from choosen years ----------

print("--- Loading data from 2025... ---")

data_2025 = load_data(DATA_2025_DIR)

print(data_2025.head())
print("Number of trips in 2025:", len(data_2025))


print("--- Loading data from 2024... ---")

data_2024 = load_data(DATA_2024_DIR)

print(data_2024.head())
print("Number of trips in 2024:", len(data_2024))


# ---------- Combining datasets ----------

print("--- Combining data from 2024 and 2025... ---")

combined_trip_data = pd.concat(
    [data_2024, data_2025],
    ignore_index=True
)

print(combined_trip_data.head())


# ---------- Basic information ----------

print("--- Basic information about combined data ---")

print("Total number of trips:", len(combined_trip_data))

print("Columns:")
print(combined_trip_data.columns)


# ---------- Loading station data from XML ----------

tree = ET.parse(STATIONS_FILE)
root = tree.getroot()


# ---------- wczytanie pliku XML ze stacjami ----------

# tree = ET.parse(STATIONS_FILE)
# root = tree.getroot()

# stations_without_geo = 0

# for i, row in data_24_25_combined.head().iterrows():
#     start_name = str(row["Start station"]).strip()
#     end_name = str(row["End station"]).strip()



#     start_station = stations_by_name.get(start_name)
#     end_station = stations_by_name.get(end_name)

#     start_lat = start_station["lat"] if start_station else "brak danych"
#     start_lon = start_station["lon"] if start_station else "brak danych"
#     end_lat = end_station["lat"] if end_station else "brak danych"
#     end_lon = end_station["lon"] if end_station else "brak danych"

#     if start_lat or start_lon or end_lat or end_lon == "brak danych":
#         print(f"Przejazd {i+1}, nie ma położenia geograficznego")
#         stations_without_geo += 1

# print(stations_without_geo)
