from pathlib import Path
import sys

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd


def _apply_project_plot_style():
    current = Path(__file__).resolve()
    for path in [current.parent, *current.parents]:
        if (path / "plot_style.py").exists():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))

            import plot_style

            plot_style.apply_montserrat_style()
            return


_apply_project_plot_style()


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
WEEKEND_NAMES = ["Saturday", "Sunday"]

DAY_TYPE_COLORS = {
    "Dni robocze": "#0057FF",
    "Weekendy": "#00A6FF",
}

DATASET_BASE_COLORS = {
    "Pełny zbiór": "#0057FF",
    "Bez nieciągłości": "#FF2E00",
}

DATASET_DAY_TYPE_COLORS = {
    "Pełny zbiór": {
        "Dni robocze": "#0057FF",
        "Weekendy": "#00A6FF",
    },
    "Bez nieciągłości": {
        "Dni robocze": "#FF2E00",
        "Weekendy": "#FFB000",
    },
}

DATASET_MARKERS = {
    "Pełny zbiór": "o",
    "Bez nieciągłości": "^",
}


def find_project_root(start=None):
    current = Path.cwd() if start is None else Path(start)
    for path in [current, *current.parents]:
        if (path / "Data").exists():
            return path
    raise FileNotFoundError("Could not find project root containing Data/")


def dataset_paths(data_dir):
    return {
        "full_dataset": data_dir / "final_trip_data.parquet",
        "without_discontinuities": data_dir / "rides_data_without_discontinuities.parquet",
    }


def dataset_base_color(dataset_name, index=0):
    if dataset_name in DATASET_BASE_COLORS:
        return DATASET_BASE_COLORS[dataset_name]

    fallback_colors = ["#0057FF", "#FF2E00", "#00A676", "#D000FF", "#111111"]
    return fallback_colors[index % len(fallback_colors)]


def dataset_day_type_colors(dataset_name, index=0):
    if dataset_name in DATASET_DAY_TYPE_COLORS:
        return DATASET_DAY_TYPE_COLORS[dataset_name]

    base_color = dataset_base_color(dataset_name, index=index)
    return {
        "Dni robocze": base_color,
        "Weekendy": lighten_color(base_color, amount=0.45),
    }


def dataset_marker(dataset_name):
    return DATASET_MARKERS.get(dataset_name, "o")


def title_range_text(lower_limit=None, upper_limit=None, range_label=None):
    if range_label:
        return f"Zakres czasu: {range_label}"

    if lower_limit is None or upper_limit is None:
        return None

    return f"Zakres czasu: {lower_limit:g}-{upper_limit:g} min"


def load_duration_data(data_file):
    dur_dist_data = pd.read_parquet(data_file)
    dur_dist_data["duration_min_bin"] = (
        np.floor(dur_dist_data["total_duration_minutes"])
    )
    dur_dist_data["duration_counts"] = (
        dur_dist_data["duration_min_bin"]
        .value_counts()
        .sort_index()
    )

    return dur_dist_data


def split_weekdays_weekends(dur_dist_data):
    dur_dist_data_weekends = dur_dist_data[
        dur_dist_data["start_day_of_week"].isin(WEEKEND_NAMES)
    ]
    dur_dist_data_weekdays = dur_dist_data[
        dur_dist_data["start_day_of_week"].isin(WEEKDAY_NAMES)
    ]

    return dur_dist_data_weekdays, dur_dist_data_weekends


def duration_quantiles(dur_dist_data):
    return dur_dist_data["total_duration_minutes"].quantile(
        [0.05, 0.5, 0.9, 0.95, 0.99, 0.999, 0.9999, 1.0]
    )


def duration_range_coverage(dur_dist_data, lower_limit=3, upper_limit=180):
    mask = (
        (dur_dist_data["total_duration_minutes"] >= lower_limit) &
        (dur_dist_data["total_duration_minutes"] <= upper_limit)
    )

    covered_count = mask.sum()
    total_count = len(dur_dist_data)
    covered_percent = covered_count / total_count * 100

    print(f"Liczba przejazdów w zakresie {lower_limit}-{upper_limit} min: {covered_count}")
    print(f"Liczba wszystkich przejazdów: {total_count}")
    print(f"Udział danych w tym zakresie: {covered_percent:.2f}%")

    return {
        "covered_count": covered_count,
        "total_count": total_count,
        "covered_percent": covered_percent,
    }


def print_min_max_duration_by_day_type(dur_dist_data_weekdays, dur_dist_data_weekends):
    print("Weekdays")
    print("Min duration [min]:", dur_dist_data_weekdays["total_duration_minutes"].min())
    print("Max duration [min]:", dur_dist_data_weekdays["total_duration_minutes"].max())

    print("---------------------------------")

    print("Weekends")
    print("Min duration [min]:", dur_dist_data_weekends["total_duration_minutes"].min())
    print("Max duration [min]:", dur_dist_data_weekends["total_duration_minutes"].max())


def count_rides_by_duration(
    dur_dist_data_weekdays,
    dur_dist_data_weekends,
    lower_limit=3,
    upper_limit=180,
):
    duration_counts_weekdays = (
        dur_dist_data_weekdays.loc[
            dur_dist_data_weekdays["total_duration_minutes"].between(
                lower_limit,
                upper_limit,
            ),
            "duration_min_bin",
        ]
        .value_counts()
        .sort_index()
    )

    duration_counts_weekends = (
        dur_dist_data_weekends.loc[
            dur_dist_data_weekends["total_duration_minutes"].between(
                lower_limit,
                upper_limit,
            ),
            "duration_min_bin",
        ]
        .value_counts()
        .sort_index()
    )

    return duration_counts_weekdays, duration_counts_weekends


def plot_duration_counts(
    duration_counts_weekdays,
    duration_counts_weekends,
    lower_limit=3,
    upper_limit=180,
    title_prefix=None,
    ax=None,
    colors=None,
    marker="o",
):
    if colors is None:
        colors = DAY_TYPE_COLORS

    if ax is None:
        _, ax = plt.subplots(figsize=(11, 6))

    ax.scatter(
        duration_counts_weekdays.index,
        duration_counts_weekdays.values,
        s=25,
        alpha=0.7,
        color=colors["Dni robocze"],
        marker=marker,
        label="Dni robocze",
    )

    ax.scatter(
        duration_counts_weekends.index,
        duration_counts_weekends.values,
        s=25,
        alpha=0.7,
        color=colors["Weekendy"],
        marker=marker,
        label="Weekendy",
    )

    ax.set_xlabel("Czas trwania przejazdu [min]")
    ax.set_ylabel("Liczba przejazdów")

    title = f"Rozkład liczby przejazdów według czasu trwania ({lower_limit}-{upper_limit} min)"
    if title_prefix:
        title = f"{title_prefix}: {title}"
    ax.set_title(title)

    ax.legend()
    ax.grid(alpha=0.25)

    ax.set_xlim(lower_limit, upper_limit)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(15))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(15))

    return ax


def prepare_duration_data(
    dur_dist_data_weekdays,
    dur_dist_data_weekends,
    lower_limit=3,
    upper_limit=180,
):
    duration_weekdays = dur_dist_data_weekdays.loc[
        dur_dist_data_weekdays["total_duration_minutes"].between(
            lower_limit,
            upper_limit,
        ),
        "total_duration_minutes",
    ]

    duration_weekends = dur_dist_data_weekends.loc[
        dur_dist_data_weekends["total_duration_minutes"].between(
            lower_limit,
            upper_limit,
        ),
        "total_duration_minutes",
    ]

    return duration_weekdays, duration_weekends


def make_log_bin_edges(min_value, max_value, a):
    bin_edges = [min_value]

    while bin_edges[-1] < max_value:
        next_edge = bin_edges[-1] * a
        bin_edges.append(min(next_edge, max_value))

    return np.array(bin_edges)


def log_binning(data, bin_edges):
    counts, edges = np.histogram(data, bins=bin_edges)
    widths = edges[1:] - edges[:-1]
    probability_density = counts / (len(data) * widths)
    bin_centers = np.sqrt(edges[:-1] * edges[1:])
    mask = probability_density > 0

    return (
        bin_centers[mask],
        probability_density[mask],
        counts[mask],
        edges,
    )


def calculate_duration_log_binning_results(
    duration_weekdays,
    duration_weekends,
    lower_limit=3,
    upper_limit=180,
    a_values=(1.5, 1.75, 2),
):
    min_time = lower_limit
    max_time = upper_limit
    results = {}

    for a_value in a_values:
        bin_edges = make_log_bin_edges(
            min_time,
            max_time,
            a_value,
        )

        x_weekdays, p_weekdays, n_weekdays, edges = log_binning(
            duration_weekdays,
            bin_edges,
        )

        x_weekends, p_weekends, n_weekends, edges = log_binning(
            duration_weekends,
            bin_edges,
        )

        results[a_value] = {
            "weekdays": {
                "x": x_weekdays,
                "p": p_weekdays,
                "n": n_weekdays,
            },
            "weekends": {
                "x": x_weekends,
                "p": p_weekends,
                "n": n_weekends,
            },
            "bin_edges": bin_edges,
        }

        print(f"\na = {a_value}")
        print("Number of bins:", len(bin_edges) - 1)
        print("First bin edges:", bin_edges[:5])
        print("Last bin edges:", bin_edges[-5:])

    return results


def plot_duration_log_probability(
    results,
    lower_limit=3,
    upper_limit=180,
    a_values=(1.5, 1.75, 2),
    title_prefix=None,
):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)

    for ax, a_value in zip(axes, a_values):
        ax.scatter(
            results[a_value]["weekdays"]["x"],
            results[a_value]["weekdays"]["p"],
            s=25,
            alpha=0.75,
            color=DAY_TYPE_COLORS["Dni robocze"],
            label="Dni robocze",
        )

        ax.scatter(
            results[a_value]["weekends"]["x"],
            results[a_value]["weekends"]["p"],
            s=25,
            alpha=0.75,
            color=DAY_TYPE_COLORS["Weekendy"],
            label="Weekendy",
        )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lower_limit, upper_limit)

        ax.set_xlabel("Czas przejazdu [min]")
        ax.set_title(f"a = {a_value}")

        ax.grid(True, axis="y", alpha=0.2, which="major")
        ax.grid(True, axis="x", alpha=0.2, which="major")
        ax.legend()

    axes[0].set_ylabel("P(t)")

    title = (
        "Wykresy prawdopodobieństwa czasu przejazdu P(t) "
        f"z binowaniem logarytmicznym ({lower_limit}-{upper_limit} min)"
    )
    if title_prefix:
        title = f"{title_prefix}: {title}"

    fig.suptitle(title, fontsize=14)
    plt.tight_layout()

    return fig, axes


def lighten_color(color, amount=0.45):
    c = np.array(mcolors.to_rgb(color))
    white = np.array([1, 1, 1])
    return tuple(c + (white - c) * amount)


def plot_duration_tail_fit(
    results,
    lower_limit=3,
    upper_limit=180,
    a_value=1.5,
    x_min=15,
    x_max=1000,
    title_prefix=None,
    ax=None,
    colors=None,
    marker="o",
):
    if colors is None:
        colors = DAY_TYPE_COLORS

    x_weekdays = results[a_value]["weekdays"]["x"]
    y_weekdays = results[a_value]["weekdays"]["p"]

    x_weekends = results[a_value]["weekends"]["x"]
    y_weekends = results[a_value]["weekends"]["p"]

    fit_colors = {
        "Dni robocze": lighten_color(colors["Dni robocze"], amount=0.35),
        "Weekendy": lighten_color(colors["Weekendy"], amount=0.35),
    }

    fit_mask_weekdays = (
        (x_weekdays > 0) &
        (y_weekdays > 0) &
        (x_weekdays >= x_min) &
        (x_weekdays <= x_max)
    )
    x_fit_data_weekdays = x_weekdays[fit_mask_weekdays]
    y_fit_data_weekdays = y_weekdays[fit_mask_weekdays]

    fit_mask_weekends = (
        (x_weekends > 0) &
        (y_weekends > 0) &
        (x_weekends >= x_min) &
        (x_weekends <= x_max)
    )
    x_fit_data_weekends = x_weekends[fit_mask_weekends]
    y_fit_data_weekends = y_weekends[fit_mask_weekends]

    log_x_weekdays = np.log10(x_fit_data_weekdays)
    log_y_weekdays = np.log10(y_fit_data_weekdays)
    slope_weekdays, intercept_weekdays = np.polyfit(
        log_x_weekdays,
        log_y_weekdays,
        1,
    )

    log_x_weekends = np.log10(x_fit_data_weekends)
    log_y_weekends = np.log10(y_fit_data_weekends)
    slope_weekends, intercept_weekends = np.polyfit(
        log_x_weekends,
        log_y_weekends,
        1,
    )

    x_fit_weekdays = np.logspace(
        np.log10(x_fit_data_weekdays.min()),
        np.log10(x_fit_data_weekdays.max()),
        200,
    )
    y_fit_weekdays = 10**intercept_weekdays * x_fit_weekdays**slope_weekdays

    x_fit_weekends = np.logspace(
        np.log10(x_fit_data_weekends.min()),
        np.log10(x_fit_data_weekends.max()),
        200,
    )
    y_fit_weekends = 10**intercept_weekends * x_fit_weekends**slope_weekends

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))

    ax.scatter(
        x_weekdays,
        y_weekdays,
        s=35,
        alpha=0.65,
        color=colors["Dni robocze"],
        marker=marker,
        label="Dni robocze",
    )

    ax.scatter(
        x_weekends,
        y_weekends,
        s=35,
        alpha=0.65,
        color=colors["Weekendy"],
        marker=marker,
        label="Weekendy",
    )

    ax.plot(
        x_fit_weekdays,
        y_fit_weekdays,
        color=fit_colors["Dni robocze"],
        linestyle="--",
        linewidth=2.2,
        alpha=0.95,
        label=f"Dopasowanie dni robocze ({x_min}-{x_max} min), nachylenie = {slope_weekdays:.3f}",
    )

    ax.plot(
        x_fit_weekends,
        y_fit_weekends,
        color=fit_colors["Weekendy"],
        linestyle="--",
        linewidth=2.2,
        alpha=0.95,
        label=f"Dopasowanie weekendy ({x_min}-{x_max} min), nachylenie = {slope_weekends:.3f}",
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lower_limit, upper_limit)

    ax.set_xlabel("Czas przejazdu [min]")
    ax.set_ylabel("P(t)")

    title = (
        "Dopasowanie ogona rozkładu czasu przejazdu P(t) "
        f"(a = {a_value}, zakres dopasowania {x_min}-{x_max} min)"
    )
    if title_prefix:
        title = f"{title_prefix}: {title}"
    ax.set_title(title, fontsize=14)

    ax.grid(True, axis="y", alpha=0.25, which="major")
    ax.grid(True, axis="x", alpha=0.20, which="major")
    ax.legend()

    print("Zakres dopasowania:")
    print(f"x_min = {x_min}")
    print(f"x_max = {x_max}")
    print()

    print("Dni robocze:")
    print(f"Nachylenie = {slope_weekdays:.3f}")
    print(f"Wyraz wolny = {intercept_weekdays:.3f}")
    print()

    print("Weekendy:")
    print(f"Nachylenie = {slope_weekends:.3f}")
    print(f"Wyraz wolny = {intercept_weekends:.3f}")

    return {
        "weekdays": {
            "slope": slope_weekdays,
            "intercept": intercept_weekdays,
            "x_fit": x_fit_weekdays,
            "y_fit": y_fit_weekdays,
        },
        "weekends": {
            "slope": slope_weekends,
            "intercept": intercept_weekends,
            "x_fit": x_fit_weekends,
            "y_fit": y_fit_weekends,
        },
        "ax": ax,
    }


def prepared_ride_distance_data(dur_dist_data):
    distance_columns = [
        "trip_id",
        "start_date",
        "end_date",
        "total_duration_minutes",
        "start_lat",
        "start_lon",
        "end_lat",
        "end_lon",
        "straight_line_distance_km",
    ]

    ride_distance_data = dur_dist_data[distance_columns].copy()
    coordinate_columns = ["start_lat", "start_lon", "end_lat", "end_lon"]
    missing_coordinates_count = ride_distance_data[coordinate_columns].isna().any(axis=1).sum()

    print(f"Liczba przejazdów: {len(ride_distance_data)}")
    print(f"Liczba przejazdów z brakującymi współrzędnymi: {missing_coordinates_count}")

    return ride_distance_data


def prepare_speed_distribution_data(dur_dist_data, lower_limit=3, upper_limit=180):
    speed_distribution_data = dur_dist_data.loc[
        dur_dist_data["total_duration_minutes"].between(lower_limit, upper_limit)
        & dur_dist_data["speed_km_per_h"].notna()
        & np.isfinite(dur_dist_data["speed_km_per_h"])
        & (dur_dist_data["speed_km_per_h"] > 0)
    ].copy()

    speed_weekdays = speed_distribution_data[
        speed_distribution_data["start_day_of_week"].isin(WEEKDAY_NAMES)
    ]

    speed_weekends = speed_distribution_data[
        speed_distribution_data["start_day_of_week"].isin(WEEKEND_NAMES)
    ]

    print(
        f"Liczba przejazdów w zakresie {lower_limit}-{upper_limit} min "
        f"z policzoną prędkością: {len(speed_distribution_data)}"
    )

    return speed_distribution_data, speed_weekdays, speed_weekends


def plot_speed_histogram(
    speed_distribution_data,
    speed_weekdays,
    speed_weekends,
    lower_limit=3,
    upper_limit=180,
    title_prefix=None,
    ax=None,
    colors=None,
):
    if colors is None:
        colors = DAY_TYPE_COLORS

    speed_plot_upper_limit = np.ceil(
        speed_distribution_data["speed_km_per_h"].quantile(0.995)
    )

    speed_hist_upper_limit = np.ceil(speed_distribution_data["speed_km_per_h"].max())
    speed_bins = np.arange(0, speed_hist_upper_limit + 1, 1)

    if ax is None:
        _, ax = plt.subplots(figsize=(11, 6))

    ax.hist(
        speed_weekdays["speed_km_per_h"],
        bins=speed_bins,
        density=True,
        alpha=0.65,
        color=colors["Dni robocze"],
        label="Dni robocze",
    )

    ax.hist(
        speed_weekends["speed_km_per_h"],
        bins=speed_bins,
        density=True,
        alpha=0.65,
        color=colors["Weekendy"],
        label="Weekendy",
    )

    ax.set_xlabel("Prędkość w linii prostej [km/h]")
    ax.set_ylabel("Gęstość prawdopodobieństwa")

    title = (
        "Rozkład prędkości przejazdów w linii prostej "
        f"({lower_limit}-{upper_limit} min)"
    )
    if title_prefix:
        title = f"{title_prefix}: {title}"
    ax.set_title(title)

    ax.set_xlim(0, speed_plot_upper_limit)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(15))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(12))

    ax.legend()
    ax.grid(alpha=0.25)

    return ax


def make_speed_log_bin_edges(min_value, max_value, a):
    bin_edges = [min_value]

    while bin_edges[-1] < max_value:
        next_edge = bin_edges[-1] * a
        bin_edges.append(min(next_edge, max_value))

    return np.array(bin_edges)


def speed_log_binning(data, bin_edges):
    counts, edges = np.histogram(data, bins=bin_edges)
    widths = edges[1:] - edges[:-1]
    probability_density = counts / (len(data) * widths)
    bin_centers = np.sqrt(edges[:-1] * edges[1:])
    mask = probability_density > 0

    return (
        bin_centers[mask],
        probability_density[mask],
        counts[mask],
        edges,
    )


def calculate_speed_log_binning_results(
    speed_distribution_data,
    speed_weekdays,
    speed_weekends,
    speed_a_values=(1.5, 1.75, 2),
):
    speed_values_weekdays = speed_weekdays["speed_km_per_h"]
    speed_values_weekends = speed_weekends["speed_km_per_h"]

    min_speed = speed_distribution_data["speed_km_per_h"].min()
    max_speed = speed_distribution_data["speed_km_per_h"].max()
    speed_results = {}

    for a_value in speed_a_values:
        speed_bin_edges = make_speed_log_bin_edges(
            min_speed,
            max_speed,
            a_value,
        )

        x_speed_weekdays, p_speed_weekdays, n_speed_weekdays, edges = speed_log_binning(
            speed_values_weekdays,
            speed_bin_edges,
        )

        x_speed_weekends, p_speed_weekends, n_speed_weekends, edges = speed_log_binning(
            speed_values_weekends,
            speed_bin_edges,
        )

        speed_results[a_value] = {
            "weekdays": {
                "x": x_speed_weekdays,
                "p": p_speed_weekdays,
                "n": n_speed_weekdays,
            },
            "weekends": {
                "x": x_speed_weekends,
                "p": p_speed_weekends,
                "n": n_speed_weekends,
            },
            "bin_edges": speed_bin_edges,
        }

        print(f"\na = {a_value}")
        print("Number of bins:", len(speed_bin_edges) - 1)
        print("First bin edges:", speed_bin_edges[:5])
        print("Last bin edges:", speed_bin_edges[-5:])

    return speed_results, min_speed, max_speed


def plot_speed_log_probability(
    speed_results,
    min_speed,
    max_speed,
    lower_limit=3,
    upper_limit=180,
    speed_a_values=(1.5, 1.75, 2),
    title_prefix=None,
):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)

    for ax, a_value in zip(axes, speed_a_values):
        ax.scatter(
            speed_results[a_value]["weekdays"]["x"],
            speed_results[a_value]["weekdays"]["p"],
            s=25,
            alpha=0.75,
            color=DAY_TYPE_COLORS["Dni robocze"],
            label="Dni robocze",
        )

        ax.scatter(
            speed_results[a_value]["weekends"]["x"],
            speed_results[a_value]["weekends"]["p"],
            s=25,
            alpha=0.75,
            color=DAY_TYPE_COLORS["Weekendy"],
            label="Weekendy",
        )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(min_speed, max_speed)

        ax.set_xlabel("Prędkość w linii prostej [km/h]")
        ax.set_title(f"a = {a_value}")

        ax.grid(True, axis="y", alpha=0.2, which="major")
        ax.grid(True, axis="x", alpha=0.2, which="major")
        ax.legend()

    axes[0].set_ylabel("P(v)")

    title = (
        "Rozkład prędkości P(v) z binowaniem logarytmicznym "
        f"({lower_limit}-{upper_limit} min, v > 0 km/h)"
    )
    if title_prefix:
        title = f"{title_prefix}: {title}"

    fig.suptitle(title, fontsize=14)
    plt.tight_layout()

    return fig, axes


def rides_with_speed_between(speed_distribution_data, low, high):
    display_columns = [
        "trip_id",
        "start_date",
        "end_date",
        "start_station_name",
        "end_station_name",
        "total_duration_minutes",
        "straight_line_distance_km",
        "speed_km_per_h",
    ]

    return (
        speed_distribution_data.loc[
            speed_distribution_data["speed_km_per_h"].between(low, high),
            display_columns,
        ]
        .sort_values("speed_km_per_h")
    )


def prepare_dataset_outputs(
    data_file,
    lower_limit=3,
    upper_limit=180,
    a_values=(1.5, 1.75, 2),
    speed_a_values=(1.5, 1.75, 2),
):
    dur_dist_data = load_duration_data(data_file)
    dur_dist_data_weekdays, dur_dist_data_weekends = split_weekdays_weekends(dur_dist_data)

    coverage = duration_range_coverage(dur_dist_data, lower_limit, upper_limit)
    duration_counts_weekdays, duration_counts_weekends = count_rides_by_duration(
        dur_dist_data_weekdays,
        dur_dist_data_weekends,
        lower_limit,
        upper_limit,
    )

    duration_weekdays, duration_weekends = prepare_duration_data(
        dur_dist_data_weekdays,
        dur_dist_data_weekends,
        lower_limit,
        upper_limit,
    )

    duration_results = calculate_duration_log_binning_results(
        duration_weekdays,
        duration_weekends,
        lower_limit,
        upper_limit,
        a_values,
    )

    speed_distribution_data, speed_weekdays, speed_weekends = prepare_speed_distribution_data(
        dur_dist_data,
        lower_limit,
        upper_limit,
    )

    speed_results, min_speed, max_speed = calculate_speed_log_binning_results(
        speed_distribution_data,
        speed_weekdays,
        speed_weekends,
        speed_a_values,
    )

    return {
        "data_file": data_file,
        "dur_dist_data": dur_dist_data,
        "dur_dist_data_weekdays": dur_dist_data_weekdays,
        "dur_dist_data_weekends": dur_dist_data_weekends,
        "coverage": coverage,
        "duration_counts_weekdays": duration_counts_weekdays,
        "duration_counts_weekends": duration_counts_weekends,
        "duration_weekdays": duration_weekdays,
        "duration_weekends": duration_weekends,
        "duration_results": duration_results,
        "speed_distribution_data": speed_distribution_data,
        "speed_weekdays": speed_weekdays,
        "speed_weekends": speed_weekends,
        "speed_results": speed_results,
        "min_speed": min_speed,
        "max_speed": max_speed,
    }


def comparison_summary(outputs_by_dataset):
    rows = []

    for dataset_name, outputs in outputs_by_dataset.items():
        rows.append({
            "dataset": dataset_name,
            "liczba_wszystkich_przejazdow": outputs["coverage"]["total_count"],
            "liczba_przejazdow_w_zakresie": outputs["coverage"]["covered_count"],
            "udzial_w_zakresie_%": outputs["coverage"]["covered_percent"],
            "liczba_przejazdow_z_predkoscia": len(outputs["speed_distribution_data"]),
            "min_speed_km_h": outputs["min_speed"],
            "max_speed_km_h": outputs["max_speed"],
        })

    return pd.DataFrame(rows)


def plot_duration_counts_dataset_comparison(
    outputs_by_dataset,
    lower_limit=3,
    upper_limit=180,
    range_label=None,
):
    fig, axes = plt.subplots(
        1,
        len(outputs_by_dataset),
        figsize=(7 * len(outputs_by_dataset), 5),
        sharex=True,
        sharey=True,
    )

    if len(outputs_by_dataset) == 1:
        axes = [axes]

    for dataset_index, (ax, (dataset_name, outputs)) in enumerate(
        zip(axes, outputs_by_dataset.items())
    ):
        plot_duration_counts(
            outputs["duration_counts_weekdays"],
            outputs["duration_counts_weekends"],
            lower_limit,
            upper_limit,
            ax=ax,
            colors=dataset_day_type_colors(dataset_name, dataset_index),
            marker=dataset_marker(dataset_name),
        )
        ax.set_title(dataset_name)

    title = "Rozkład liczby przejazdów według czasu trwania"
    range_text = title_range_text(lower_limit, upper_limit, range_label)
    if range_text:
        title = f"{title}\n{range_text}"

    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    return fig, axes


def plot_duration_log_probability_dataset_comparison(
    outputs_by_dataset,
    a_value=1.5,
    lower_limit=3,
    upper_limit=180,
    range_label=None,
):
    fig, axes = plt.subplots(
        1,
        len(outputs_by_dataset),
        figsize=(7 * len(outputs_by_dataset), 5),
        sharex=True,
        sharey=True,
    )

    if len(outputs_by_dataset) == 1:
        axes = [axes]

    for dataset_index, (ax, (dataset_name, outputs)) in enumerate(
        zip(axes, outputs_by_dataset.items())
    ):
        results = outputs["duration_results"]
        colors = dataset_day_type_colors(dataset_name, dataset_index)
        marker = dataset_marker(dataset_name)

        ax.scatter(
            results[a_value]["weekdays"]["x"],
            results[a_value]["weekdays"]["p"],
            s=25,
            alpha=0.75,
            color=colors["Dni robocze"],
            marker=marker,
            label="Dni robocze",
        )
        ax.scatter(
            results[a_value]["weekends"]["x"],
            results[a_value]["weekends"]["p"],
            s=25,
            alpha=0.75,
            color=colors["Weekendy"],
            marker=marker,
            label="Weekendy",
        )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lower_limit, upper_limit)
        ax.set_xlabel("Czas przejazdu [min]")
        ax.set_title(dataset_name)
        ax.grid(True, axis="y", alpha=0.2, which="major")
        ax.grid(True, axis="x", alpha=0.2, which="major")
        ax.legend()

    axes[0].set_ylabel("P(t)")
    title = "Wykresy prawdopodobieństwa czasu przejazdu P(t) z binowaniem logarytmicznym"
    range_text = title_range_text(lower_limit, upper_limit, range_label)
    if range_text:
        title = f"{title}\n{range_text}, a = {a_value}"
    else:
        title = f"{title}\na = {a_value}"

    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.88))

    return fig, axes


def plot_speed_histogram_dataset_comparison(
    outputs_by_dataset,
    lower_limit=3,
    upper_limit=180,
    range_label=None,
):
    fig, axes = plt.subplots(
        1,
        len(outputs_by_dataset),
        figsize=(7 * len(outputs_by_dataset), 5),
        sharex=True,
        sharey=True,
    )

    if len(outputs_by_dataset) == 1:
        axes = [axes]

    for dataset_index, (ax, (dataset_name, outputs)) in enumerate(
        zip(axes, outputs_by_dataset.items())
    ):
        plot_speed_histogram(
            outputs["speed_distribution_data"],
            outputs["speed_weekdays"],
            outputs["speed_weekends"],
            lower_limit,
            upper_limit,
            ax=ax,
            colors=dataset_day_type_colors(dataset_name, dataset_index),
        )
        ax.set_title(dataset_name)

    title = "Rozkład prędkości przejazdów w linii prostej"
    range_text = title_range_text(lower_limit, upper_limit, range_label)
    if range_text:
        title = f"{title}\n{range_text}"

    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    return fig, axes


def plot_speed_log_probability_dataset_comparison(
    outputs_by_dataset,
    a_value=1.5,
    range_label=None,
):
    fig, axes = plt.subplots(
        1,
        len(outputs_by_dataset),
        figsize=(7 * len(outputs_by_dataset), 5),
        sharey=True,
    )

    if len(outputs_by_dataset) == 1:
        axes = [axes]

    for dataset_index, (ax, (dataset_name, outputs)) in enumerate(
        zip(axes, outputs_by_dataset.items())
    ):
        speed_results = outputs["speed_results"]
        colors = dataset_day_type_colors(dataset_name, dataset_index)
        marker = dataset_marker(dataset_name)

        ax.scatter(
            speed_results[a_value]["weekdays"]["x"],
            speed_results[a_value]["weekdays"]["p"],
            s=25,
            alpha=0.75,
            color=colors["Dni robocze"],
            marker=marker,
            label="Dni robocze",
        )
        ax.scatter(
            speed_results[a_value]["weekends"]["x"],
            speed_results[a_value]["weekends"]["p"],
            s=25,
            alpha=0.75,
            color=colors["Weekendy"],
            marker=marker,
            label="Weekendy",
        )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(outputs["min_speed"], outputs["max_speed"])
        ax.set_xlabel("Prędkość w linii prostej [km/h]")
        ax.set_title(dataset_name)
        ax.grid(True, axis="y", alpha=0.2, which="major")
        ax.grid(True, axis="x", alpha=0.2, which="major")
        ax.legend()

    axes[0].set_ylabel("P(v)")
    title = "Rozkład prędkości P(v) z binowaniem logarytmicznym"
    range_text = title_range_text(range_label=range_label)
    if range_text:
        title = f"{title}\n{range_text}, a = {a_value}"
    else:
        title = f"{title}\na = {a_value}"

    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.88))

    return fig, axes


def plot_duration_log_probability_dataset_overlay(
    outputs_by_dataset,
    a_value=1.5,
    lower_limit=3,
    upper_limit=180,
    range_label=None,
):
    fig, ax = plt.subplots(figsize=(9, 6))

    day_type_labels = {
        "weekdays": "Dni robocze",
        "weekends": "Weekendy",
    }

    for dataset_index, (dataset_name, outputs) in enumerate(outputs_by_dataset.items()):
        results = outputs["duration_results"]
        colors = dataset_day_type_colors(dataset_name, dataset_index)
        marker = dataset_marker(dataset_name)

        for day_type in ["weekdays", "weekends"]:
            day_type_label = day_type_labels[day_type]
            ax.scatter(
                results[a_value][day_type]["x"],
                results[a_value][day_type]["p"],
                s=28,
                alpha=0.72 if day_type == "weekdays" else 0.52,
                color=colors[day_type_label],
                marker=marker,
                label=f"{dataset_name} - {day_type_label}",
            )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lower_limit, upper_limit)
    ax.set_xlabel("Czas przejazdu [min]")
    ax.set_ylabel("P(t)")
    title = "Porównanie P(t) dla dwóch zbiorów danych,"
    range_text = title_range_text(lower_limit, upper_limit, range_label)
    if range_text:
        title = f"{title}\n{range_text}"
    else:
        title = f"{title}\n "

    ax.set_title(title, fontsize=14)
    ax.grid(True, axis="y", alpha=0.2, which="major")
    ax.grid(True, axis="x", alpha=0.2, which="major")
    ax.legend()
    plt.tight_layout()

    return fig, ax


def plot_speed_log_probability_dataset_overlay(
    outputs_by_dataset,
    a_value=1.5,
    range_label=None,
):
    fig, ax = plt.subplots(figsize=(9, 6))

    day_type_labels = {
        "weekdays": "Dni robocze",
        "weekends": "Weekendy",
    }

    min_speed = min(outputs["min_speed"] for outputs in outputs_by_dataset.values())
    max_speed = max(outputs["max_speed"] for outputs in outputs_by_dataset.values())

    for dataset_index, (dataset_name, outputs) in enumerate(outputs_by_dataset.items()):
        speed_results = outputs["speed_results"]
        colors = dataset_day_type_colors(dataset_name, dataset_index)
        marker = dataset_marker(dataset_name)

        for day_type in ["weekdays", "weekends"]:
            day_type_label = day_type_labels[day_type]
            ax.scatter(
                speed_results[a_value][day_type]["x"],
                speed_results[a_value][day_type]["p"],
                s=28,
                alpha=0.72 if day_type == "weekdays" else 0.52,
                color=colors[day_type_label],
                marker=marker,
                label=f"{dataset_name} - {day_type_label}",
            )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(min_speed, max_speed)
    ax.set_xlabel("Prędkość w linii prostej [km/h]")
    ax.set_ylabel("P(v)")
    title = "Porównanie P(v) dla dwóch zbiorów danych,"
    range_text = title_range_text(range_label=range_label)
    if range_text:
        title = f"{title}\n{range_text}"
    else:
        title = f"{title}\n"

    ax.set_title(title, fontsize=14)
    ax.grid(True, axis="y", alpha=0.2, which="major")
    ax.grid(True, axis="x", alpha=0.2, which="major")
    ax.legend()
    plt.tight_layout()

    return fig, ax


def clean_numeric_values(values):
    numeric_values = pd.to_numeric(values, errors="coerce")
    numeric_values = numeric_values[
        numeric_values.notna()
        & np.isfinite(numeric_values)
    ]

    return numeric_values.to_numpy(dtype=float)


def sample_numeric_values(values, sample_size=1_000_000, random_state=42):
    if sample_size is None or len(values) <= sample_size:
        return values

    rng = np.random.default_rng(random_state)
    sample_indices = rng.choice(len(values), size=sample_size, replace=False)

    return values[sample_indices]


def empirical_ks_statistic(values_a, values_b):
    values_a = np.sort(values_a)
    values_b = np.sort(values_b)

    combined_values = np.sort(np.concatenate([values_a, values_b]))
    cdf_a = np.searchsorted(values_a, combined_values, side="right") / len(values_a)
    cdf_b = np.searchsorted(values_b, combined_values, side="right") / len(values_b)

    return np.max(np.abs(cdf_a - cdf_b))


def empirical_wasserstein_distance(values_a, values_b):
    values_a = np.sort(values_a)
    values_b = np.sort(values_b)

    combined_values = np.sort(np.concatenate([values_a, values_b]))
    value_deltas = np.diff(combined_values)

    if len(value_deltas) == 0:
        return 0.0

    cdf_a = np.searchsorted(values_a, combined_values[:-1], side="right") / len(values_a)
    cdf_b = np.searchsorted(values_b, combined_values[:-1], side="right") / len(values_b)

    return np.sum(np.abs(cdf_a - cdf_b) * value_deltas)


def jensen_shannon_distance(values_a, values_b, bins=200, log_bins=True):
    min_value = min(values_a.min(), values_b.min())
    max_value = max(values_a.max(), values_b.max())

    if min_value == max_value:
        return 0.0

    if log_bins and min_value > 0:
        bin_edges = np.geomspace(min_value, max_value, bins + 1)
    else:
        bin_edges = np.linspace(min_value, max_value, bins + 1)

    counts_a, _ = np.histogram(values_a, bins=bin_edges)
    counts_b, _ = np.histogram(values_b, bins=bin_edges)

    probabilities_a = counts_a / counts_a.sum()
    probabilities_b = counts_b / counts_b.sum()
    mean_probabilities = 0.5 * (probabilities_a + probabilities_b)

    def kl_divergence(probabilities, reference):
        mask = probabilities > 0
        return np.sum(
            probabilities[mask] * np.log2(probabilities[mask] / reference[mask])
        )

    js_divergence = 0.5 * (
        kl_divergence(probabilities_a, mean_probabilities)
        + kl_divergence(probabilities_b, mean_probabilities)
    )

    return np.sqrt(js_divergence)


def values_for_distribution_difference(
    outputs,
    variable,
    subset,
    lower_limit=3,
    upper_limit=180,
):
    if variable == "total_duration_minutes":
        if subset == "all":
            data = outputs["dur_dist_data"]
            return data.loc[
                data["total_duration_minutes"].between(lower_limit, upper_limit),
                "total_duration_minutes",
            ]
        if subset == "weekdays":
            return outputs["duration_weekdays"]
        if subset == "weekends":
            return outputs["duration_weekends"]

    if variable == "speed_km_per_h":
        if subset == "all":
            return outputs["speed_distribution_data"]["speed_km_per_h"]
        if subset == "weekdays":
            return outputs["speed_weekdays"]["speed_km_per_h"]
        if subset == "weekends":
            return outputs["speed_weekends"]["speed_km_per_h"]

    raise ValueError(f"Unsupported variable/subset combination: {variable}, {subset}")


def distribution_difference_summary(
    outputs_by_dataset,
    lower_limit=3,
    upper_limit=180,
    variables=("total_duration_minutes", "speed_km_per_h"),
    subsets=("all", "weekdays", "weekends"),
    sample_size=1_000_000,
    random_state=42,
    js_bins=200,
    percentiles=(0.5, 0.9, 0.95, 0.99, 0.999),
):
    if len(outputs_by_dataset) != 2:
        raise ValueError("distribution_difference_summary expects exactly two datasets.")

    dataset_names = list(outputs_by_dataset.keys())
    dataset_a_name, dataset_b_name = dataset_names
    outputs_a = outputs_by_dataset[dataset_a_name]
    outputs_b = outputs_by_dataset[dataset_b_name]

    rows = []

    for variable in variables:
        for subset in subsets:
            values_a = clean_numeric_values(
                values_for_distribution_difference(
                    outputs_a,
                    variable,
                    subset,
                    lower_limit=lower_limit,
                    upper_limit=upper_limit,
                )
            )
            values_b = clean_numeric_values(
                values_for_distribution_difference(
                    outputs_b,
                    variable,
                    subset,
                    lower_limit=lower_limit,
                    upper_limit=upper_limit,
                )
            )

            if len(values_a) == 0 or len(values_b) == 0:
                continue

            sample_a = sample_numeric_values(
                values_a,
                sample_size=sample_size,
                random_state=random_state,
            )
            sample_b = sample_numeric_values(
                values_b,
                sample_size=sample_size,
                random_state=random_state + 1,
            )

            row = {
                "variable": variable,
                "subset": subset,
                "dataset_a": dataset_a_name,
                "dataset_b": dataset_b_name,
                "n_a": len(values_a),
                "n_b": len(values_b),
                "sample_n_a": len(sample_a),
                "sample_n_b": len(sample_b),
                "ks_statistic": empirical_ks_statistic(sample_a, sample_b),
                "wasserstein_distance": empirical_wasserstein_distance(sample_a, sample_b),
                "js_distance": jensen_shannon_distance(
                    values_a,
                    values_b,
                    bins=js_bins,
                    log_bins=True,
                ),
                "mean_a": values_a.mean(),
                "mean_b": values_b.mean(),
                "mean_diff_b_minus_a": values_b.mean() - values_a.mean(),
            }

            for percentile in percentiles:
                percentile_label = f"p{percentile * 100:g}"
                percentile_a = np.quantile(values_a, percentile)
                percentile_b = np.quantile(values_b, percentile)
                row[f"{percentile_label}_a"] = percentile_a
                row[f"{percentile_label}_b"] = percentile_b
                row[f"{percentile_label}_diff_b_minus_a"] = percentile_b - percentile_a

            rows.append(row)

    return pd.DataFrame(rows)
