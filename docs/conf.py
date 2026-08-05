import os
import sys

# resolve relative to this file's own location, not the CWD Sphinx happens to be run from
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

project = "CFT"
copyright = "SADC Climate Services Centre"
author = "Piotr Wolski, Sunshine Gamedze"

try:
    from importlib.metadata import version as _version
    release = _version("sadc-cft")
except Exception:
    release = "0.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",   # supports Google/NumPy-style docstrings
    "sphinx.ext.viewcode",   # adds links to highlighted source
    "myst_parser",           # lets .md files (e.g. README) be included alongside .rst
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# --- autodoc behaviour ---

# Only document things we explicitly reference with autofunction/automodule below -
# nothing gets pulled in automatically, so internal/GUI-only helpers never leak into the docs
autodoc_default_options = {
    "members": False,
}

# If NOT using the conda-based RTD build (docs/environment.yml), these heavy/native
# dependencies won't be installed in the docs build environment. Mocking them lets
# autodoc still import each functions_*.py module to pull out docstrings, without
# needing GDAL/PyQt5/etc. actually installed and working.
#
# Remove this list entirely if you switch to the conda-based .readthedocs.yaml instead.
autodoc_mock_imports = [
    "osgeo",
    "cartopy",
    "PyQt5",
    "rasterio",
    "rasterstats",
    "geopandas",
    "rioxarray",
    "geocube",
    "netCDF4",
]
