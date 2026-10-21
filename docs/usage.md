# Running CFT

Always activate the CFT environment first:

```bash
mamba activate cft-env
```

## With the graphical interface

Open the main CFT window, from which every module can be started:

```bash
cft
```

or `python -m cft`.

Each module can also be opened directly:

| Module | Command | Equivalent |
|---|---|---|
| Download | `download-tool` | `python -m cft.download` |
| Forecast | `forecast-tool` | `python -m cft.forecast` |
| Products (observed) | `products_obs-tool` | `python -m cft.products_obs` |
| Zoning | `zoning-tool` | `python -m cft.zoning` |
| Verification | `verification-tool` | `python -m cft.verification` |
| Synthesis | `synthesis-tool` | `python -m cft.synthesis` |

## Without the graphical interface

The main computation of each module can be called from Python with a dictionary of settings, called `config`. This is useful for scripts, batch runs and notebooks. The settings are the same as in the graphical interface, and the interface saves them to a json file that can be reused.

### Forecast

```python
from cft.functions.functions_forecast import computeModelNoGui

config = {
    'rootDir': '../test',
    'predictorYear': 2026,
    'predictorMonth': 'Jun',
    'fcstTargetSeas': 'Aug-Oct',
    'fcstTargetYear': 2026,
    'climStartYr': 1994,
    'climEndYr': 2015,
    'predictorExtents': {'minLon': -180.0, 'maxLon': 180.0, 'minLat': -60.0, 'maxLat': 60.0},
    'predictorFileName': '../test/GPH850_System9_CDS_Jun_s300s200e150e250_1981-2026.nc',
    'predictorVar': 'z',
    'predictorCode': 'z',
    'crossval': 'KF',
    'preproc': 'PCR',
    'regression': 'OLS',
    'timeAggregation': 'mean',
    'predictandFileName': '../test/PRCP_CHIRPSp25_IRIDL_Aug-Oct_s340s200e150e250_1981-2025.nc',
    'predictandVar': 'prcp',
    'predictandCategory': 'temperature',
    'predictandMissingValue': '-999',
    'zonesFile': None,
    'zonesAttribute': 'Name',
    'zonesAggregate': False,
    'regridPredictand': False,
    'overlayFile': '../gis/sadc/gadm41_ZAF_1.json',
}

computeModelNoGui(config)
```

### Products (observed)

```python
from cft.functions.functions_products_obs import computeProductsObsNoGui

config = {
    'outDir': '../output',
    'obsFile': '../test/PRCP_CHIRPS_daily_1981-2025.nc',  # .nc (grid) or .csv (stations)
    'obsVar': 'prcp',                                     # ignored for csv
    'obsMissingValue': '',                                # e.g. '-999', '' if none
    'obsDsetCode': 'chirps',                              # used in output file names
    'climStartYr': 1991,
    'climEndYr': 2020,
    # agronomic onset
    'regimeFile': '',                                     # '' - derive regime from data
    'onsetAnchorMonth': {'summer': 10, 'winter': 3},      # season start month
    'onsetWindowDays': {'summer': 123, 'winter': 153},    # onset search window, days
    # DWTP
    'dwtpSaveFiltered': False,                            # save filtered daily rainfall
    'parallelize': True,
    'products': {'onsetTadross': True, 'onsetMalawi': True, 'onsetZambia': False,
                 'onsetAccum': True, 'onsetDWTP': True},
}

computeProductsObsNoGui(config)
```

Settings saved by the graphical interface to a json file can be run from the command line:

```bash
python -m cft.functions.functions_products_obs products.json
```

See the [API reference](api.rst) for the functions' arguments.
