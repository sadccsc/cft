# CFT — Climate Forecasting Toolbox

A Python package for statistical seasonal climate forecasting, developed by the SADC Climate Services Centre (CSC).

[![PyPI](https://img.shields.io/pypi/v/sadc-cft)](https://pypi.org/project/sadc-cft/)
[![Read the Docs](https://img.shields.io/readthedocs/sadc-cft)](https://sadc-cft.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

CFT downloads predictor and predictand data, builds and cross-validates statistical forecast models, and derives rainy season characteristics such as onset from observed daily rainfall. It can be used through graphical interfaces or from Python.

**Documentation: [sadc-cft.readthedocs.io](https://sadc-cft.readthedocs.io)**

## Installation

```bash
mamba create --name cft-env python=3.12
mamba activate cft-env
pip install sadc-cft
```

The zoning module also needs GDAL. See the [installation guide](https://sadc-cft.readthedocs.io/en/latest/installation.html) for this and other details.

## Quick start

```bash
cft
```

opens the main CFT window. See [Running CFT](https://sadc-cft.readthedocs.io/en/latest/usage.html) for the individual modules and for use without the graphical interface.

## Authors

Piotr Wolski (wolski@csag.uct.ac.za) and Sunshine Gamedze (sgamedze@sadc.int). Original developer (2017–2022): Thembani Moitlhobogi. See [Credits and history](https://sadc-cft.readthedocs.io/en/latest/credits.html) for contributors and funding.

## Licence

MIT.
