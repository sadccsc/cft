# Installation

CFT is installed with `pip` into a dedicated Python environment. Python 3.12 is recommended.

## 1. Set up a Python environment

You need one of these environment managers:

- [Miniforge](https://github.com/conda-forge/miniforge), which installs both Conda and Mamba (recommended)
- [Anaconda](https://www.anaconda.com/download/success), the full framework, over 1 GB
- [Micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html), lightweight, for advanced users

Create and activate an environment for CFT:

```bash
mamba create --name cft-env python=3.12
mamba activate cft-env
```

With Anaconda, use `conda` instead of `mamba` in all commands on this page.

## 2. Install CFT

```bash
pip install sadc-cft
```

This installs CFT and all the packages it needs, except GDAL (see below). The download, forecast and products modules work with this installation.

## 3. Optional: install the zoning module

The zoning module needs GDAL, a geospatial library that `pip` cannot install reliably. Install it from conda-forge first, then install CFT with the `zoning` option:

```bash
mamba install -c conda-forge gdal=3.13.2
pip install "sadc-cft[zoning]"
```

You can do this at any time, including after a standard installation. Without GDAL, all other modules work, and the zoning module shows a message that GDAL is missing.

## 4. Check the installation

```bash
python -m cft
```

This should open the main CFT window.

## Upgrading

```bash
mamba activate cft-env
pip install --upgrade sadc-cft
```

If you installed the zoning module, upgrade with `pip install --upgrade "sadc-cft[zoning]"`.

## Requirements

All other dependencies are installed automatically by `pip`. They include `numpy`, `pandas`, `xarray`, `scipy`, `scikit-learn`, `geopandas`, `rioxarray`, `rasterio`, `rasterstats`, `geocube`, `shapely`, `netCDF4`, `cftime`, `joblib`, `matplotlib`, `cartopy`, `PyQt5` and `cdsapi`. The full list is in the package's `pyproject.toml`.
