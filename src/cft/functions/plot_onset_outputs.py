"""
Quick-look maps of every variable in CFT products output files (gridded netCDF).

Each variable is saved to its own image, <output name>_<variable>.png.
A variable with a time-like extra dimension (season, years) is drawn as one
panel per value of that dimension in the same image. Any other extra dimension
(sea, Stats, ...) is split into separate images, <file stem>_<variable>_<value>.png,
so that each image has one colour scale for one quantity.
"""
import os
import re
import textwrap
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:          # plots are drawn without coastlines
    ccrs = None

# Colour maps by variable name. Rules are checked in order; the first regular
# expression that matches the variable name is used.
#   kind: "seq" - sequential, autoscaled to the 2nd-98th percentile
#         "div" - diverging, symmetric around 0
#         "cyc" - cyclic, fixed range (calendar day of year or dekad)
#         "cat" - categorical, one colour per integer value
CMAPS = [
    (r"Anom$",                         "PuOr_r",   "div"),   # timing anomalies (onset, demise)
    (r"^(wetTotal|dryTotal|duration)Anom$", "BrBG", "div"),
    (r"Doy(Clim)?$",                   "twilight", "cyc"),
    (r"Dekad(Clim)?$",                 "twilight", "cyc"),
    (r"^(regime|status|anchorMonth|anchorDay)$", "tab10", "cat"),
    (r"(wetTotal|dryTotal|TotPrecip|PrecipRate|PrecipInt|^rm$|FrcWetDays)", "YlGnBu", "seq"),
    (r"(FrcDryDays|DrySpell)",         "YlOrBr",   "seq"),
    (r"WetSpell",                      "PuBuGn",   "seq"),
    (r"(SinceAnchor|duration|Length|FirstDay|^w0$|clmEnv)", "viridis", "seq"),
    (r".*",                            "viridis",  "seq"),   # anything else
]

try:
    from cft.functions.functions_products_obs import showMessage
except ImportError:
    def showMessage(message, type="RUNTIME"):
        print(message)

CYCLIC_RANGE = {"Doy": (1, 366), "Dekad": (1, 36)}
SPATIAL_DIMS = ("lat", "lon")


def _style(name, cmaps):
    for pattern, cmap, kind in cmaps:
        if re.search(pattern, name):
            return cmap, kind
    return "viridis", "seq"


def _norm_kwargs(da, name, cmap, kind):
    vals = da.values[np.isfinite(da.values)]
    if kind == "cyc":
        key = "Doy" if "Doy" in name else "Dekad"
        vmin, vmax = CYCLIC_RANGE[key]
        return dict(cmap=cmap, vmin=vmin, vmax=vmax)
    if kind == "cat":
        levels = np.unique(vals)
        bounds = np.concatenate([levels - 0.5, [levels[-1] + 0.5]])
        cm = plt.get_cmap(cmap, len(levels))
        return dict(cmap=cm, norm=BoundaryNorm(bounds, cm.N),
                    cbar_kwargs={"ticks": levels})
    if kind == "div":
        lim = np.nanpercentile(np.abs(vals), 98) or 1
        return dict(cmap=cmap, vmin=-lim, vmax=lim)
    vmin, vmax = np.nanpercentile(vals, [2, 98])
    if vmin == vmax:
        vmin, vmax = vmin - 1, vmax + 1
    return dict(cmap=cmap, vmin=vmin, vmax=vmax)


def plotVariable(da, name, outfile, cmaps=CMAPS, title="", caption=""):
    """Plot one gridded variable to outfile. Returns False if it was skipped."""
    if not all(d in da.dims for d in SPATIAL_DIMS):
        return False
    if not np.issubdtype(da.dtype, np.number) or np.issubdtype(da.dtype, np.timedelta64):
        return False                       # dates are shown through the Doy variables
    if not np.isfinite(da.values).any():
        return False

    extra = [d for d in da.dims if d not in SPATIAL_DIMS]
    if len(extra) > 1:
        return False
    da = da.transpose(*extra, "lat", "lon")

    cmap, kind = _style(name, cmaps)
    kw = _norm_kwargs(da, name, cmap, kind)
    units = da.attrs.get("units", "")
    kw.setdefault("cbar_kwargs", {})["label"] = "{} {}".format(name, "({})".format(units) if units else "").strip()

    if ccrs is not None:
        kw["transform"] = ccrs.PlateCarree()
        kw["subplot_kws"] = {"projection": ccrs.PlateCarree()}

    if not extra:
        if ccrs is not None:
            fig, ax = plt.subplots(figsize=(6, 5), subplot_kw=kw.pop("subplot_kws"))
        else:
            fig, ax = plt.subplots(figsize=(6, 5))
        da.plot(ax=ax, **kw)
        axes = [ax]
        ax.set_title(title or name)
    else:
        n = da.sizes[extra[0]]
        aspect = da.sizes["lon"] / da.sizes["lat"]
        g = da.plot(col=extra[0], col_wrap=min(6, n), **kw, size=2.2,
                    aspect=max(0.5, min(2, aspect)))
        axes = g.axs.flat
        fig = g.fig
        fig.suptitle(title or name, y=1.02)

    # every panel shows the data domain (half a grid cell beyond the outer cell
    # centres); without this, coastlines can widen faceted maps to the globe
    lat, lon = da["lat"].values, da["lon"].values
    dlat = abs(lat[1] - lat[0]) / 2 if lat.size > 1 else 0.5
    dlon = abs(lon[1] - lon[0]) / 2 if lon.size > 1 else 0.5
    extent = [lon.min() - dlon, lon.max() + dlon, lat.min() - dlat, lat.max() + dlat]
    for ax in axes:
        if ax is None:
            continue
        if ccrs is not None and hasattr(ax, "coastlines"):
            ax.coastlines(linewidth=0.5)
            ax.add_feature(cfeature.BORDERS, linewidth=0.3)
            ax.set_extent(extent, crs=ccrs.PlateCarree())
        else:
            ax.set_xlim(extent[0], extent[1])
            ax.set_ylim(extent[2], extent[3])

    if caption:
        fig.text(0.5, 0, textwrap.fill(caption, 110), ha="center", va="top", fontsize=8)
    fig.savefig(outfile, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return True


FACET_DIMS = ("season", "years", "time")


def _split(da, name):
    """Split a variable along every extra dimension that is not time-like
    (sea, Stats, ...), so that each piece has at most a time-like dimension.
    Yields (name, DataArray)."""
    splittable = [d for d in da.dims if d not in SPATIAL_DIMS and d not in FACET_DIMS]
    if not splittable:
        yield name, da
        return
    dim = splittable[0]
    for value in da[dim].values:
        sub = da.sel({dim: value})
        if dim in sub.coords:
            sub = sub.drop_vars(dim)
        if isinstance(value, bytes):
            value = value.decode()
        label = value if isinstance(value, str) else "{}{}".format(dim, value)
        yield from _split(sub, "{}_{}".format(name, label))


def plotOutput(ds, path, cmaps=CMAPS, fmt="png", caption=""):
    """Plot every variable of an output dataset, one image per variable.

    ds    xarray Dataset as written to the output file (gridded, lat/lon)
    path  output path without extension, as passed to the write functions;
          images are written next to it as <path>_<variable>.png
    Station output (no lat/lon dimensions) is not plotted.
    Returns the list of image files written.
    """
    path = Path(path)
    written = []
    for var in ds.data_vars:
        for name, da in _split(ds[var], var):
            outfile = path.with_name("{}_{}.{}".format(path.name, name, fmt))
            if plotVariable(da, name, outfile, cmaps,
                            title="{}: {}".format(path.name, name), caption=caption):
                written.append(outfile)
    return written


def locationToGrid(ds, meta):
    """Rebuild the lat/lon grid from data with a location dimension,
    as in writeLocationOutput."""
    if isinstance(ds, xr.DataArray):
        ds = ds.to_dataset(name=ds.name or "value")
    extra = [c for c in ds.coords if c not in ds.dims and c not in ("lat", "lon")]
    ds = ds.drop_vars(extra)
    out = ds.set_index(location=["lat", "lon"]).unstack("location")
    return out.reindex(lat=meta["lat"], lon=meta["lon"]).transpose(..., "lat", "lon")


def plotLocationOutput(ds, meta, path, description, settings, cmaps=CMAPS, fmt="png"):
    """Plot output with a location dimension; counterpart of writeLocationOutput,
    called with the same arguments. Images are written next to the output as
    <path>_<variable>.png, with the description as a caption.
    Station output is not plotted. Returns the list of image files written.
    """
    if meta["type"] != "grid":
        return []
    written = plotOutput(locationToGrid(ds, meta), path, cmaps, fmt, caption=description)
    for outFile in written:
        showMessage("Plotted {}".format(outFile), "INFO")
    return written


def plotOutputFile(ncfile, outdir=None, cmaps=CMAPS, fmt="png"):
    """Plot every variable of a netCDF output file already on disk."""
    ncfile = Path(ncfile)
    outdir = Path(outdir) if outdir else ncfile.parent
    outdir.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(ncfile, decode_timedelta=False) as ds:
        return plotOutput(ds, outdir / ncfile.stem, cmaps, fmt)


def plotOutputDir(directory, outdir=None, cmaps=CMAPS, fmt="png"):
    """Plot every netCDF file in a directory."""
    written = []
    for ncfile in sorted(Path(directory).glob("*.nc")):
        written += plotOutputFile(ncfile, outdir, cmaps, fmt)
    return written
