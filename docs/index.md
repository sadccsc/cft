# CFT — Climate Forecasting Toolbox

CFT is a Python package for statistical seasonal climate forecasting, developed by the SADC Climate Services Centre (CSC). It downloads predictor and predictand data, builds and cross-validates statistical forecast models, and derives rainy season characteristics such as onset from observed daily rainfall.

CFT can be used through graphical interfaces, or called directly from Python and the command line.

## Modules

| Module | Description |
|---|---|
| [Download](modules/download.md) | Downloads predictor and predictand data from the Copernicus Climate Data Store (CDS), IRIDL and JMA, and converts them to a format CFT reads |
| [Forecast](modules/forecast.md) | Builds and cross-validates statistical seasonal forecast models, deterministic and probabilistic |
| [Products (observed)](modules/products.md) | Derives onset, demise, duration and dry-to-wet transition statistics from observed daily rainfall |
| Zoning | Groups station data into forecast zones |
| Verification | Verifies forecast skill |
| Synthesis | Combines forecast outputs |

The zoning, verification and synthesis modules are not yet documented here.

## Where to start

1. [Install CFT](installation.md).
2. If you will download data from the CDS, [set up your CDS account and API key](modules/download.md#setting-up-access-to-the-cds).
3. Read [how to run CFT](usage.md), with or without the graphical interface.

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
usage
```

```{toctree}
:maxdepth: 2
:caption: Modules

modules/download
modules/forecast
modules/products
```

```{toctree}
:maxdepth: 1
:caption: Reference

examples
api
references
credits
```

## Indices

* {ref}`genindex`
* {ref}`modindex`
* {ref}`search`
