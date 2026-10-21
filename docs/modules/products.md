# Products (observed)

The products module, new in version 7.0, derives rainy season characteristics from observed **daily** rainfall. It offers three groups of methods:

| Group | Products | Approach |
|---|---|---|
| [Agronomic onset](#agronomic-onset) | onset by national and published definitions | first day on which a rainfall threshold is reached, within a season set for each rainfall regime |
| [Anomalous accumulation](#onset-and-demise-from-anomalous-accumulation) | onset, demise, duration, wet and dry season rainfall | turning points of cumulative rainfall anomalies, within a water year derived from the annual cycle |
| [Dry-to-wet transition period (DWTP)](#dry-to-wet-transition-period-dwtp) | DWTP statistics and climatological envelope | transition from dry to wet conditions within climatological envelopes; up to two rainy seasons per year |

## Input data and common settings

**Input data:**

- **Gridded data** — a netCDF file with daily rainfall, dimensions (time, lat, lon).
- **Station data** — a CSV file with dates in the first column and one column per station. The top three rows hold the station ID, latitude and longitude (`ID`, `Lat`, `Lon`), as for station data in the forecast module.

Grid cells and stations without any data are skipped. Values equal to the missing value code you set are treated as missing.

**Climatological period** — the start and end year you set. It is used to derive rainfall regimes, water years and climatological envelopes, and to calculate climatologies and anomalies. It must lie within the period covered by the data, and may cover all of it.

**Seasons** are labelled with the year in which they start.

**Output** — gridded input gives netCDF files on the same grid as the input. Station input gives one CSV file per output variable, with the same `ID`/`Lat`/`Lon` header rows as the input. Locations that were not processed have missing values. Each output file carries a `description` attribute with the definition of its product.

**Parallel processing** — calculations can run in parallel over locations, using a fraction of the available CPUs (`fractionCpus` in `DEFAULT_SETTINGS`, in `functions_products_obs.py`).

## Agronomic onset

### Rainfall regime

Onset is calculated separately for summer and winter rainfall locations. The regime of each location is either:

- **derived from the data** — a location has *summer rainfall* if at least ⅔ of its annual rainfall in the climatological period falls in October–March, *winter rainfall* if at least ⅔ falls in April–September, and *all-year rainfall* otherwise; or
- **read from a regime map** — a netCDF file coded 1 for summer and 2 for winter rainfall. Any other value is treated as all-year rainfall.

Onset is not calculated for all-year rainfall locations. Negative rainfall values are treated as missing.

### Season

For each regime you set the month in which the season starts and the length of the onset search window. The start month should fall in the dry season, before any plausible onset. Onset is searched for from day 1 of that month until the end of the window.

| Regime | Default season start | Default search window |
|---|---|---|
| Summer rainfall | 1 October | 123 days (to 31 January) |
| Winter rainfall | 1 March | 153 days (to 31 July) |

For example, the summer season 2020 starts on 1 October 2020.

### Onset definitions

The definitions are those used by SADC national meteorological services, as reported in a 2026 survey, and the definition of Tadross et al. (2005). Several countries use Tadross et al. or Sivakumar (1988) (the Botswana definition) as their main or secondary definition.

```{include} _onset_definitions.md
```

Accumulations are trailing sums, and the onset day is the day on which the threshold is reached. The exception is the Namibia definition, where onset is the first day of the 10-day window. Unless stated otherwise, a dry day is a day with less than 1 mm of rainfall.

### Outputs

One file per selected definition, named `<code>_<product>`:

| Variable | Dimensions | Description |
|---|---|---|
| `onsetDate` | season, location | date of onset |
| `onsetDoy` | season, location | day of the calendar year of onset (1–366) |
| `onsetDekad` | season, location | dekad of the calendar year of onset (1–36) |
| `onsetDaysSinceAnchor` | season, location | days from the season start to onset (0 = season start) |
| `onsetDekadsSinceAnchor` | season, location | dekads from the season start to onset |
| `onsetDoyClim`, `onsetDekadClim` | location | climatological onset, as day of year and dekad |
| `onsetDoyAnom`, `onsetDekadAnom` | season, location | onset anomaly in days and in dekads; positive values mean later than normal |
| `anchorDate` | season, location | start date of the season |
| `regime` | location | rainfall regime: 1 — summer, 2 — winter |
| `anchorMonth` | location | season start month |

Seasons in which no onset is found within the search window have missing values, as do seasons with missing data.

The **climatology** is the mean onset over the climatological period, excluding seasons without onset. Climatology and anomalies are calculated on days counted from the season start, so they are not affected by the turn of the year in summer seasons.

### Files for forecasting

For gridded input, each definition also produces up to two files for use as a predictand in the [forecast module](forecast.md), one per rainfall regime:

- `<code>_<product>_summer_forforecast.nc`
- `<code>_<product>_winter_forforecast.nc`

Each holds `onsetDaysSinceAnchor` for the locations of that regime only, with the `season` dimension replaced by `time`. The time of each season is its anchor date, the season start (by default 1 October for summer and 1 March for winter rainfall). A file is not written if its regime has no data.

When you use one of these files in the forecast module, set the forecast target season to the anchor month: `Oct` for the default summer file, `Mar` for the default winter file. The forecast is then a forecast of the number of days from the season start to onset.

## Onset and demise from anomalous accumulation

Onset and demise are the turning points of the cumulative daily rainfall anomaly (Liebmann and Marengo, 2001), within a water year derived from harmonic analysis of the annual cycle (Dunning et al., 2016). The implementation follows Zilli et al. (2026).

- **Water year** — for each location, the mean annual cycle of daily rainfall in the climatological period (29 February excluded) is decomposed into harmonics. If the annual harmonic explains more variance than the semi-annual and the third harmonic, the location has a single rainy season, and its water year starts at the minimum of the annual harmonic (`w0`). Locations without a single rainy season are not processed.
- **Anomaly** — daily rainfall minus the mean daily rainfall of the climatological period (`rm`).
- **Onset** — minimum of the smoothed cumulative anomaly, accumulated forward over the first 182 days of the water year.
- **Demise** — minimum of the smoothed cumulative anomaly, accumulated backward over the last 182 days of the water year.
- **Smoothing** — zero-phase Butterworth low-pass filter (order 2, filter parameter 18), which removes variations shorter than about 36 days.

If rainfall stays below the long-term mean throughout the onset search period, the minimum, and so the onset, falls on the last day of that period.

Each water year is labelled with the year in which it starts. Only complete water years are processed.

### Outputs

File `<code>_onsetAccum`:

| Variable | Dimensions | Description |
|---|---|---|
| `onsetDate`, `demiseDate` | season, location | date of onset and demise |
| `onsetDoy`, `demiseDoy` | season, location | day of the calendar year (1–366) |
| `onsetDekad`, `demiseDekad` | season, location | dekad of the calendar year (1–36) |
| `onsetDaysSinceAnchor`, `demiseDaysSinceAnchor` | season, location | days from the start of the water year |
| `onsetDoyClim`, `onsetDekadClim`, `demiseDoyClim`, `demiseDekadClim` | location | climatology, as day of year and dekad |
| `onsetDoyAnom`, `onsetDekadAnom`, `demiseDoyAnom`, `demiseDekadAnom` | season, location | anomaly in days and in dekads; positive values mean later than normal |
| `duration` | season, location | days from onset to demise |
| `wetTotal` | season, location | rainfall from onset to demise (mm) |
| `dryTotal` | season, location | rainfall from the day after the previous season's demise to the day before onset (mm); missing in the first season |
| `durationClim`, `wetTotalClim`, `dryTotalClim` | location | climatological means |
| `durationAnom`, `wetTotalAnom`, `dryTotalAnom` | season, location | anomalies |
| `anchorDate` | season, location | start date of the water year |
| `w0` | location | start of the water year, day of year (no-leap calendar) |
| `anchorMonth`, `anchorDay` | location | start of the water year as month and day |
| `rm` | location | mean daily rainfall in the climatological period (mm/day) |

Climatologies are means over the climatological period. As for agronomic onset, onset and demise climatologies and anomalies are calculated on days counted from the start of the water year.

Method settings in `DEFAULT_SETTINGS`: `accumWindowDays` (365), `accumOnsetDays` (182), `accumDemiseDays` (182), `accumCutoff` (18).

## Dry-to-wet transition period (DWTP)

The DWTP is the period in which a location changes from dry to wet conditions (Zilli et al., 2026). The method can find up to two rainy seasons per year, so it can be used where rainfall is bimodal.

- **Transition days** — daily rainfall is smoothed with a Butterworth low-pass filter (filter parameter 60), which removes variations shorter than about 120 days. Days on which smoothed rainfall is positive and increasing are transition days; runs of at least 30 such days are transition periods.
- **Climatological envelope** — for each day of the year, the frequency of transition periods in the climatological period is calculated. The start of the water year (`w0`) is the day with the lowest frequency. Envelopes are the parts of the year in which the normalised, smoothed frequency is at least 0.5. Up to two envelopes are kept; a second envelope is dropped if its mean smoothed rainfall is less than 35% of that of the first.
- **DWTP in each year** — within each envelope, the end of the DWTP is the day by which 50% of the envelope's rainfall has fallen, moved later past long dry breaks. The start of the DWTP is the end of the longest dry break early in the envelope.
- **Statistics** — rainfall and wet and dry spell statistics for each DWTP.

The implementation reproduces the reference code of the method. Known inconsistencies of that code are kept and marked in the source (`kernels_dwtp.py`). Data should start on 1 January and have no missing days; locations with missing data are not processed. 29 February is excluded from all calculations.

### Outputs

`<code>_onsetDWTP_Stats` — DWTP statistics, dimensions years, sea (season: 0, 1), location:

| Variable | Units | Description |
|---|---|---|
| `FirstDay` | day of year | first day of the DWTP (see notes below) |
| `Length` | days | duration of the DWTP |
| `OnsIntensity` | mm/day per day | mean gradient of the filtered rainfall during the DWTP |
| `TotPrecip` | mm | total rainfall during the DWTP |
| `PrecipRate` | mm/day | rainfall rate during the DWTP |
| `PrecipInt` | mm/wet day | rainfall per wet day |
| `FrcWetDays`, `FrcDryDays` | % | fraction of wet and dry days |
| `LengthWetSpells`, `LengthDrySpells` | days | mean duration of wet and dry spells |
| `MaxWetSpell`, `MaxDrySpell` | days | longest wet and dry spell |

`<code>_onsetDWTP_ClmEnvelope` — climatological envelope:

| Variable | Dimensions | Description |
|---|---|---|
| `clmEnv` | season, Stats (FirstDay, Length), location | first day of year and length of each climatological envelope |
| `w0` | location | start of the water year, day of year |
| `status` | location | 0 — ok; 1 — no transition periods found; 2 — not processed (e.g. missing data); 3 — ok, with a warning from the envelope detection |

`<code>_onsetDWTP_PR60` — the filtered daily rainfall (`bwpp`). It is written only if selected (`dwtpSaveFiltered`), as the file is as large as the input data.

Notes, as in the reference code:

- `FirstDay` is counted from 0 in most years and from 1 in the first year, and can exceed 365 when the envelope starts in the next calendar year.
- Each DWTP is assigned to the calendar year in which its envelope starts.
- When only one climatological envelope is found, both rows of `clmEnv` hold that envelope.
- Wet days are days with rainfall above 0 mm, dry days with 0 mm.

Method settings in `DEFAULT_SETTINGS`: `dwtpFilterWindow` (60), `dwtpMinLength` (30), `dwtpMaxSeasons` (2).

## Running without the graphical interface

See [Running CFT](../usage.md#products-observed) for an example `config`, and the [API reference](../api.rst) for `computeProductsObsNoGui`.
