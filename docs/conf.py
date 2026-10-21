# Sphinx configuration for the CFT documentation.
# Merge the marked sections into your existing conf.py if it has other settings.

import inspect
import os
import re
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "CFT — Climate Forecasting Toolbox"
author = "SADC Climate Services Centre"

extensions = [
    "myst_parser",            # pages written in Markdown
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3

html_theme = "sphinx_rtd_theme"

# generated include files are not pages of their own
exclude_patterns = ["_build", "modules/_*.md"]

# --- GDAL is needed only by the zoning module, and is not installed on the
# --- documentation build server
autodoc_mock_imports = ["osgeo"]


# --- onset definitions table, generated from the docstrings of the onset
# --- functions each time the documentation is built
ONSET_MODULE = "cft.functions.kernels_onset_agro"
ONSET_TABLE = os.path.join(os.path.dirname(__file__), "modules", "_onset_definitions.md")


def _label(name):
    # onsetSouthAfrica -> South Africa, onsetTadross -> Tadross et al.
    label = re.sub(r"(?<!^)(?=[A-Z])", " ", name[len("onset"):])
    return "Tadross et al." if label == "Tadross" else label


def write_onset_table(app):
    import importlib

    try:
        module = importlib.import_module(ONSET_MODULE)
    except ImportError as err:
        text = "*Onset definitions could not be loaded: {}*\n".format(err)
    else:
        rows = []
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if func.__module__ != module.__name__ or not name.startswith("onset"):
                continue
            doc = inspect.getdoc(func)
            if doc:
                rows.append((_label(name), name, " ".join(doc.split())))
        # Tadross first, then countries in alphabetical order
        rows.sort(key=lambda r: (r[1] != "onsetTadross", r[0]))
        lines = ["| Definition | Product | Rule |", "|---|---|---|"]
        lines += ["| {} | `{}` | {} |".format(*r) for r in rows]
        text = "\n".join(lines) + "\n"
    with open(ONSET_TABLE, "w") as f:
        f.write(text)


def setup(app):
    app.connect("builder-inited", write_onset_table)
