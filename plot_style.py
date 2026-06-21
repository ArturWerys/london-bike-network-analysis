from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager


# ---------- FONT CONFIG ----------

PLOT_FONT_FAMILY = "Montserrat"

PLOT_FONT_FALLBACKS = [
    PLOT_FONT_FAMILY,
    "DejaVu Sans",
    "Arial",
    "Helvetica",
    "Liberation Sans",
    "sans-serif",
]

# 400 = Regular
# 500 = Medium
# 600 = SemiBold
# 700 = Bold
# 800 = ExtraBold
# 900 = Black
PLOT_FONT_WEIGHT = 600

PROJECT_FONT_DIR = Path(__file__).resolve().parent / "fonts"

_PROJECT_FONTS_REGISTERED = False


def register_project_fonts():
    """
    Rejestruje lokalne fonty z folderu fonts/.
    Obsługuje pliki .ttf oraz .otf.
    """
    global _PROJECT_FONTS_REGISTERED

    if _PROJECT_FONTS_REGISTERED:
        return

    if PROJECT_FONT_DIR.exists():
        font_paths = sorted(PROJECT_FONT_DIR.glob("*.ttf"))
        font_paths += sorted(PROJECT_FONT_DIR.glob("*.otf"))

        for font_path in font_paths:
            font_manager.fontManager.addfont(str(font_path))

    _PROJECT_FONTS_REGISTERED = True


def apply_montserrat_style():
    """
    Ustawia globalny styl wykresów Matplotlib:
    - font Montserrat,
    - pogrubienie Bold,
    - czarny kolor tekstu,
    - wysoką jakość eksportu.
    """
    register_project_fonts()

    plt.rcParams.update(
        {
            # ---------- FONT ----------
            "font.family": "sans-serif",
            "font.sans-serif": PLOT_FONT_FALLBACKS,
            "font.weight": PLOT_FONT_WEIGHT,

            # ---------- JAKOŚĆ ----------
            "figure.dpi": 180,
            "savefig.dpi": 300,

            # ---------- EKSPORT ----------
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",

            # ---------- TYTUŁY I ETYKIETY ----------
            "axes.titleweight": PLOT_FONT_WEIGHT,
            "axes.labelweight": PLOT_FONT_WEIGHT,

            "axes.titlesize": 13,
            "axes.labelsize": 11,

            # ---------- KOLOR TEKSTU ----------
            "text.color": "black",
            "axes.titlecolor": "black",
            "axes.labelcolor": "black",
            "xtick.color": "black",
            "ytick.color": "black",
            "legend.labelcolor": "black",

            # ---------- KOLOR OSI ----------
            "axes.edgecolor": "black",

            # ---------- TICKI ----------
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,

            # ---------- LEGENDA ----------
            "legend.fontsize": 9,
            "legend.title_fontsize": 10,

            # ---------- ZAPISYWANIE ----------
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.08,
        }
    )
