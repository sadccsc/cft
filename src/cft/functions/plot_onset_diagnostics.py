"""
Onset diagnostics.

runAllDiagnostics      compares all agronomic onset definitions at one location in
                       one season, one panel per definition, in a single image:
                       <outDir>/<code>_onsetDiagnostics_<lat>_<lon>_<year>.png
plotOnsetDiagnostics   one definition at one location in every season, from
                       the CFT output: <path>_diag_<lat>_<lon>.png

Based on compare_agro_location.py (N. Hart).

Config keys (saved by the GUI, also usable without the GUI):
    diagAll    True to run the comparison of all definitions
    diagLat    latitude of the location (decimal degrees)
    diagLon    longitude of the location (decimal degrees)
    diagYear   year in which the season starts
"""
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from cft.functions import kernels_onset_agro

try:
    from cft.functions.functions_products_obs import showMessage
except ImportError:
    def showMessage(message, type="RUNTIME"):
        print(message)


# Parameters used only to draw each definition:
#   rule       short description
#   accum      accumulation period (days)
#   threshold  rainfall needed in that period (mm)
#   check      days checked after onset (dry spell, or follow-up rainfall for Angola)
#   forward    True if onset is the FIRST day of the accumulation period (Namibia)
# Order: Tadross first, then countries alphabetically.
DIAG_PARAMS = {
    "onsetTadross":     dict(accum=10, threshold=25, check=0,  rule="25 mm in 10 days"),
    "onsetAngola":      dict(accum=10, threshold=25, check=20, rule="25 mm in 10 days, followed by 20 mm in the next 20 days"),
    "onsetBotswana":    dict(accum=3,  threshold=20, check=30, rule="20 mm in 3 days, no 7-day dry spell in the following 30 days"),
    "onsetEswatini":    dict(accum=3,  threshold=20, check=0,  rule="20 mm in 3 days"),
    "onsetLesotho":     dict(accum=5,  threshold=25, check=21, rule="more than 25 mm in 5 days, no 10-day dry spell in the following 21 days"),
    "onsetMadagascar":  dict(accum=2,  threshold=20, check=30, rule="20 mm in 2 days, no dry spell longer than 10 days in the following 30 days"),
    "onsetMalawi":      dict(accum=3,  threshold=25, check=21, rule="25 mm in 3 days, no 10-day dry spell in the following 21 days"),
    "onsetMozambique":  dict(accum=3,  threshold=20, check=21, rule="20 mm in 3 days, no 10-day dry spell in the following 21 days"),
    "onsetNamibia":     dict(accum=10, threshold=10, check=0,  rule="10 mm in 10 days starting on a rainy day, with at least 2 rainy days", forward=True),
    "onsetSouthAfrica": dict(accum=5,  threshold=25, check=21, rule="25 mm in 5 days, no 10-day dry spell in the following 21 days"),
    "onsetTanzania":    dict(accum=4,  threshold=20, check=30, rule="more than 20 mm in 4 days with 2 wet days, no 10-day dry spell in the following 30 days"),
    "onsetZambia":      dict(accum=5,  threshold=20, check=21, rule="20 mm in 5 days with 3 rainy days, no dry spell longer than 10 days in the following 21 days"),
    "onsetZimbabwe":    dict(accum=2,  threshold=20, check=30, rule="20 mm in 2 days, no 10-day dry spell in the following 30 days"),
}

LOOKAHEAD = 31   # days of data after the search window, for the check after a late onset

COLORS = dict(rain="#4a7fb5", accum="#e08a2c", check="#9aa5ad", onset="#c0392b", sum="#333333")


# ------------------------------------------------------------------ location
def checkDiagLocation(config, meta):
    """Check the diagnostics location against the data domain and return the
    nearest grid cell or station as (lat, lon, label), or None after an error
    message. meta as used by writeLocationOutput."""
    try:
        lat = float(config["diagLat"])
        lon = float(config["diagLon"])
    except (KeyError, TypeError, ValueError):
        showMessage("Diagnostics location: latitude and longitude must be numbers", "ERROR")
        return None

    lats = np.asarray(meta["lat"], dtype=float)
    lons = np.asarray(meta["lon"], dtype=float)
    if meta["type"] == "grid":
        dlat = abs(lats[1] - lats[0]) / 2 if lats.size > 1 else 0.5
        dlon = abs(lons[1] - lons[0]) / 2 if lons.size > 1 else 0.5
        latmin, latmax = lats.min() - dlat, lats.max() + dlat
        lonmin, lonmax = lons.min() - dlon, lons.max() + dlon
    else:
        latmin, latmax = lats.min() - 0.5, lats.max() + 0.5
        lonmin, lonmax = lons.min() - 0.5, lons.max() + 0.5

    if not (latmin <= lat <= latmax and lonmin <= lon <= lonmax):
        showMessage("Diagnostics location {:.3f}, {:.3f} is outside the data domain: "
                    "latitude {:.2f} to {:.2f}, longitude {:.2f} to {:.2f}".format(
                        lat, lon, latmin, latmax, lonmin, lonmax), "ERROR")
        return None

    if meta["type"] == "grid":
        clat = lats[np.argmin(np.abs(lats - lat))]
        clon = lons[np.argmin(np.abs(lons - lon))]
        label = "grid cell {:.3f}, {:.3f}".format(clat, clon)
    else:
        dx = (lons - lon) * np.cos(np.radians(lat))
        dist = 111.2 * np.hypot(dx, lats - lat)
        k = int(np.argmin(dist))
        clat, clon = lats[k], lons[k]
        label = "station {} ({:.3f}, {:.3f}), {:.0f} km from the requested location".format(
            meta["ids"][k], clat, clon, dist[k])
    showMessage("Diagnostics location: {}".format(label), "INFO")
    return float(clat), float(clon), label


def selectLocation(da, lat, lon):
    """One location from data with a location dimension and lat/lon coordinates;
    None if that location is not in the data."""
    idx = np.where(np.isclose(da["lat"].values, lat) & np.isclose(da["lon"].values, lon))[0]
    if idx.size == 0:
        return None
    return da.isel(location=int(idx[0]))


def rainAtLocation(data, lat, lon):
    """Daily rainfall of one location, from data with a location dimension
    (lat/lon coordinates) or with lat/lon dimensions."""
    if "location" in data.dims:
        return selectLocation(data, lat, lon)
    return data.sel(lat=lat, lon=lon, method="nearest")


def regimeAt(rain, climStartYr, climEndYr):
    """Rainfall regime of one location, by the rule used for agronomic onset:
    1 summer (at least 2/3 of annual rainfall in Oct-Mar), 2 winter (at least
    2/3 in Apr-Sep), 0 all-year."""
    r = rain.sel(time=slice(str(climStartYr), str(climEndYr)))
    total = float(r.sum())
    if not total > 0:
        return 0
    summer = float(r.where(r["time"].dt.month.isin([10, 11, 12, 1, 2, 3])).sum())
    if summer >= 2 / 3 * total:
        return 1
    if total - summer >= 2 / 3 * total:
        return 2
    return 0


# ------------------------------------------------------------------ drawing
def _running(x, n, forward):
    """n-day rainfall total ending on (or, forward, starting on) each day."""
    s = pd.Series(x).rolling(n, min_periods=n).sum().values
    if forward:
        s = np.concatenate([s[n - 1:], np.full(n - 1, np.nan)])
    return s


def _drawPanel(ax, t, x, anchor, d, p, windowDays):
    """Daily rainfall, running total, threshold and onset in one panel.
    d = onset in days since anchor (NaN: missing data; outside window: no onset).
    Returns a short status text."""
    forward = p.get("forward", False)
    ax.bar(t, x, width=1.0, color=COLORS["rain"], alpha=0.75)
    ax.axvline(anchor + pd.Timedelta(days=windowDays), color="k", lw=0.6, ls=":")
    ax2 = ax.twinx()
    ax2.plot(t, _running(x, p["accum"], forward), color=COLORS["sum"], lw=0.8)
    ax2.axhline(p["threshold"], color=COLORS["sum"], lw=0.6, ls="--")
    ax2.tick_params(labelsize=7)
    ax2.set_ylim(bottom=0)

    if np.isfinite(d) and 0 <= d < windowDays:
        od = anchor + pd.Timedelta(days=int(d))
        if forward:
            a0, a1, c0 = od, od + pd.Timedelta(days=p["accum"] - 1), None
        else:
            a0, a1 = od - pd.Timedelta(days=p["accum"] - 1), od
            c0 = od + pd.Timedelta(days=1)
        ax.axvspan(a0 - pd.Timedelta(hours=12), a1 + pd.Timedelta(hours=12),
                   color=COLORS["accum"], alpha=0.3, lw=0)
        if p["check"] and c0 is not None:
            ax.axvspan(c0 - pd.Timedelta(hours=12), c0 + pd.Timedelta(days=p["check"] - 1, hours=12),
                       color=COLORS["check"], alpha=0.25, lw=0)
        ax.axvline(od, color=COLORS["onset"], lw=1.2)
        status = "onset {} (day {})".format(od.strftime("%d %b"), int(d))
    elif np.isfinite(d):
        status = "no onset in search window"
    else:
        status = "missing data"

    ax.set_xlim(t[0] - pd.Timedelta(days=1), t[-1] + pd.Timedelta(days=1))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.tick_params(labelsize=7)
    ax.set_ylim(bottom=0)
    return status


def _legend(fig, p_check=True, accum_label="running total (right axis)"):
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS["rain"], alpha=0.75),
               plt.Line2D([], [], color=COLORS["sum"], lw=0.8),
               plt.Line2D([], [], color=COLORS["sum"], lw=0.6, ls="--"),
               plt.Rectangle((0, 0), 1, 1, color=COLORS["accum"], alpha=0.3),
               plt.Rectangle((0, 0), 1, 1, color=COLORS["check"], alpha=0.25),
               plt.Line2D([], [], color=COLORS["onset"], lw=1.2),
               plt.Line2D([], [], color="k", lw=0.6, ls=":")]
    names = ["daily rainfall", accum_label, "threshold", "accumulation period",
             "period checked after onset", "onset", "end of search window"]
    if not p_check:
        handles.pop(4); names.pop(4)
    fig.legend(handles, names, loc="lower center", ncol=len(names), fontsize=8, frameon=False)


# ------------------------------------------------------------------ all definitions, one season
def compareOnsetDefinitions(rain, year, anchorMonth, windowDays, outfile, label="", regimeName=""):
    """Run every agronomic onset definition on one location's daily rainfall for
    the season starting on day 1 of anchorMonth in year, and plot them one above
    the other. Returns the image file, or None if the season is not covered by
    the data."""
    anchor = pd.Timestamp(year=int(year), month=int(anchorMonth), day=1)
    end = anchor + pd.Timedelta(days=windowDays + LOOKAHEAD)
    times = pd.to_datetime(rain["time"].values)
    if anchor < times[0] or end - pd.Timedelta(days=1) > times[-1]:
        showMessage("Diagnostics: season {} ({} to {}) is not fully covered by the data ({} to {})".format(
            year, anchor.date(), (end - pd.Timedelta(days=1)).date(), times[0].date(), times[-1].date()), "ERROR")
        return None
    sel = (times >= anchor) & (times < end)
    t, x = times[sel], rain.values[sel].astype(float)

    names = [n for n in DIAG_PARAMS if hasattr(kernels_onset_agro, n)]
    fig, axs = plt.subplots(len(names), 1, figsize=(10, 1.55 * len(names) + 1.4), sharex=True)
    axs = np.atleast_1d(axs)
    for ax, name in zip(axs, names):
        p = DIAG_PARAMS[name]
        d = getattr(kernels_onset_agro, name)(x)
        status = _drawPanel(ax, t, x, anchor, d, p, windowDays)
        country = re.sub(r"(?<!^)(?=[A-Z])", " ", name[len("onset"):])
        country = "Tadross et al." if country == "Tadross" else country
        ax.set_title("{}: {}  |  {}".format(country, p["rule"], status), fontsize=8.5, loc="left")
        ax.set_ylabel("mm/day", fontsize=7)

    title = "Onset definitions at {}, season {}".format(label or "", year)
    sub = "{}season start {}, search window {} days".format(
        regimeName + " rainfall, " if regimeName else "", anchor.strftime("%d %b %Y"), windowDays)
    fig.suptitle(title + "\n" + sub, fontsize=11)
    _legend(fig)
    fig.tight_layout(rect=(0, 0.025, 1, 0.98))
    fig.savefig(outfile, dpi=110)
    plt.close(fig)
    return Path(outfile)


def runAllDiagnostics(config, settings, data, meta, outDir, dsetCode):
    """Comparison of all agronomic onset definitions at the location and season
    in config (diagLat, diagLon, diagYear). Independent of the products selected.

    data   daily rainfall, with a time dimension and either a location dimension
           (lat/lon coordinates) or lat/lon dimensions
    meta   as used by writeLocationOutput
    Returns the image file, or None after an error message.
    """
    loc = checkDiagLocation(config, meta)
    if loc is None:
        return None
    lat, lon, label = loc
    try:
        year = int(config["diagYear"])
    except (KeyError, TypeError, ValueError):
        showMessage("Diagnostics: the season year must be a whole number, e.g. 2020", "ERROR")
        return None

    rain = rainAtLocation(data, lat, lon)
    if rain is None or not np.isfinite(rain.values).any():
        showMessage("Diagnostics: no data at {}".format(label), "ERROR")
        return None

    regime = regimeAt(rain, config["climStartYr"], config["climEndYr"])
    if regime == 0:
        showMessage("Diagnostics: {} has all-year rainfall; using the summer season settings".format(label), "NONCRITICAL")
    regimeName = "winter" if regime == 2 else "summer"
    anchorMonth = settings["onsetAnchorMonth"][regimeName]
    windowDays = settings["onsetWindowDays"][regimeName]

    outfile = Path(outDir) / "{}_onsetDiagnostics_{:.2f}_{:.2f}_{}.png".format(dsetCode, lat, lon, year)
    f = compareOnsetDefinitions(rain, year, anchorMonth, windowDays, outfile, label, regimeName)
    if f is not None:
        showMessage("Plotted {}".format(f), "INFO")
    return f


# ------------------------------------------------------------------ one definition, all seasons
def plotOnsetDiagnostics(rain, resloc, product, path, lat, lon, windowDays,
                         description="", label="", maxSeasons=None):
    """One definition at one location in every season, from the CFT output
    (resloc: output at the location, with anchorDate and onsetDaysSinceAnchor).
    Returns the image file, or None if nothing could be plotted."""
    p = DIAG_PARAMS.get(product)
    if p is None or "anchorDate" not in resloc or "onsetDaysSinceAnchor" not in resloc:
        return None

    seasons = resloc["season"].values
    if maxSeasons:
        seasons = seasons[-maxSeasons:]
    anchors = pd.to_datetime(resloc["anchorDate"].sel(season=seasons).values)
    onsets = resloc["onsetDaysSinceAnchor"].sel(season=seasons).values.astype(float)
    keep = ~pd.isna(anchors)
    seasons, anchors, onsets = seasons[keep], anchors[keep], onsets[keep]
    if len(seasons) == 0:
        return None

    times = pd.to_datetime(rain["time"].values)
    values = rain.values.astype(float)
    span = windowDays + max(p["check"], 10)

    ncols = 3 if len(seasons) > 4 else 1
    nrows = int(np.ceil(len(seasons) / ncols))
    fig, axs = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 1.9 * nrows + 1.2), squeeze=False)
    for ax in axs.flat[len(seasons):]:
        ax.set_visible(False)
    for ax, season, a, d in zip(axs.flat, seasons, anchors, onsets):
        sel = (times >= a) & (times < a + pd.Timedelta(days=span))
        if not sel.any():
            ax.text(0.5, 0.5, "no data", transform=ax.transAxes, ha="center", va="center")
            ax.set_title(str(season), fontsize=9)
            continue
        status = _drawPanel(ax, times[sel], values[sel], a, d, p, windowDays)
        ax.set_title("{}: {}".format(season, status), fontsize=9)
    for ax in axs[:, 0]:
        ax.set_ylabel("rain (mm/day)", fontsize=8)

    name = re.sub(r"(?<!^)(?=[A-Z])", " ", product[len("onset"):]) if product.startswith("onset") else product
    title = "{} onset at {}".format(name, label or "{:.2f}, {:.2f}".format(lat, lon))
    sub = textwrap.fill(description, 140) if description else ""
    fig.suptitle(title + ("\n" + sub if sub else ""), fontsize=11)
    _legend(fig, p["check"] > 0, "{}-day total (right axis)".format(p["accum"]))
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    path = Path(path)
    outfile = path.with_name("{}_diag_{:.2f}_{:.2f}.png".format(path.name, lat, lon))
    showMessage(outfile)
    fig.savefig(outfile, dpi=110)
    plt.close(fig)
    return outfile


# ------------------------------------------------------------------ GUI code
# In populateGui():
#
#     gl.window.checkBox_plotmaps.setChecked(bool(gl.config.get("plotMaps", False)))
#     gl.window.checkBox_diagall.setChecked(bool(gl.config.get("diagAll", False)))
#     gl.window.lineEdit_diaglat.setText(str(gl.config.get("diagLat", "")))
#     gl.window.lineEdit_diaglon.setText(str(gl.config.get("diagLon", "")))
#     gl.window.lineEdit_diagyear.setText(str(gl.config.get("diagYear", "")))
#     setDiagEnabled(gl.window.checkBox_diagall.isChecked())
#
# In readGUI():
#
#     gl.config["plotMaps"] = gl.window.checkBox_plotmaps.isChecked()
#     gl.config["diagAll"] = gl.window.checkBox_diagall.isChecked()
#     gl.config["diagLat"] = gl.window.lineEdit_diaglat.text().strip()
#     gl.config["diagLon"] = gl.window.lineEdit_diaglon.text().strip()
#     gl.config["diagYear"] = gl.window.lineEdit_diagyear.text().strip()
#
# In MainWindow.__init__():
#
#     self.checkBox_diagall.toggled.connect(setDiagEnabled)
#
# Next to populateGui():
#
#     def setDiagEnabled(enabled):
#         for w in (gl.window.label_diaglat, gl.window.lineEdit_diaglat,
#                   gl.window.label_diaglon, gl.window.lineEdit_diaglon,
#                   gl.window.label_diagyear, gl.window.lineEdit_diagyear):
#             w.setEnabled(enabled)
#
# In makeConfig():
#
#     gl.config["plotMaps"] = False
#     gl.config["diagAll"] = False
#     gl.config["diagLat"] = ""
#     gl.config["diagLon"] = ""
#     gl.config["diagYear"] = ""
