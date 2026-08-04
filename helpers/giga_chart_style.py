"""
Giga chart style (Giga Product Design System) — fonts, palette, matplotlib defaults.

Importing this module applies the style (rcParams, font registration, and the
Manrope suptitle patch). Import the GIGA_* constants for explicit colors:

    from giga_chart_style import *
"""
from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt

import matplotlib.font_manager as fm
from cycler import cycler

for _f in (list(Path.home().glob('Library/Fonts/Manrope-*.ttf'))
           + list(Path.home().glob('Library/Fonts/OpenSans-*.ttf'))):
    try:
        fm.fontManager.addfont(str(_f))
    except Exception:
        pass

# Giga palette (hex tokens straight from the design system)
GIGA_PRIMARY = {50: '#eaf2ff', 100: '#d4e5ff', 200: '#bfd7ff', 300: '#a9caff', 400: '#7eb0ff',
                500: '#5495ff', 600: '#277aff', 700: '#0050e6', 800: '#002d9c', 900: '#002d76'}
GIGA_GREY    = {50: '#fafafa', 100: '#f4f4f4', 200: '#e9e9e9', 300: '#dfdfdf', 400: '#cacaca',
                500: '#989898', 600: '#6f6f6f', 700: '#525252', 800: '#393939', 900: '#161616'}
GIGA_BLUE   = GIGA_PRIMARY[600]                       # base brand blue
GIGA_GOOD, GIGA_MODERATE, GIGA_BAD = '#00d661', '#ffc93d', '#ed1c24'   # connectivity status
# Bad -> good ramp for ordinal quality tiers (insufficient -> advanced)
GIGA_TIER_RAMP = ['#ed1c24', '#ffc93d', '#33ff8f', '#00d661']
# Categorical sequence for multi-series charts (blue ramp + grey)
GIGA_CYCLE = ['#277aff', '#0050e6', '#7eb0ff', '#002d9c', '#a9caff', '#989898', '#5495ff', '#525252']

plt.rcParams.update({
    'font.family':       'Open Sans',
    'font.sans-serif':   ['Open Sans', 'Helvetica', 'Arial', 'sans-serif'],
    'font.weight':       400,
    'figure.figsize':    [12, 6],
    'figure.dpi':        110,
    'savefig.dpi':       200,
    'figure.facecolor':  'white',
    'savefig.facecolor': 'white',
    'savefig.bbox':      'tight',
    'axes.titleweight':  600,
    'axes.titlesize':    13,
    'axes.titlecolor':   GIGA_GREY[900],
    'axes.labelcolor':   GIGA_GREY[800],
    'axes.labelweight':  500,
    'axes.edgecolor':    GIGA_GREY[300],
    'axes.linewidth':    0.8,
    'axes.grid':         True,
    'grid.color':        GIGA_GREY[200],
    'grid.alpha':        0.7,
    'grid.linewidth':    0.6,
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.prop_cycle':   cycler(color=GIGA_CYCLE),
    'text.color':        GIGA_GREY[900],
    'xtick.color':       GIGA_GREY[700],
    'ytick.color':       GIGA_GREY[700],
    'xtick.labelcolor':  GIGA_GREY[700],
    'ytick.labelcolor':  GIGA_GREY[700],
    'legend.frameon':    False,
})

# Manrope (weight 500) for figure suptitles, per the design system's heading rule
GIGA_SUPTITLE = fm.FontProperties(family='Manrope', weight=500, size=15)
from matplotlib.figure import Figure as _GigaFig
if not hasattr(_GigaFig, '_pristine_suptitle'):
    _GigaFig._pristine_suptitle = _GigaFig.suptitle
    def _giga_suptitle(self, t='', **kw):
        if 'fontproperties' not in kw and 'font' not in kw:
            kw['fontproperties'] = GIGA_SUPTITLE
        return _GigaFig._pristine_suptitle(self, t, **kw)
    _GigaFig.suptitle = _giga_suptitle


__all__ = ["GIGA_PRIMARY", "GIGA_GREY", "GIGA_BLUE", "GIGA_GOOD", "GIGA_MODERATE",
           "GIGA_BAD", "GIGA_TIER_RAMP", "GIGA_CYCLE", "GIGA_SUPTITLE"]
