# Download

The download module fetches predictor and predictand data and converts them to a format the rest of CFT reads. Data are saved to a directory you choose.

## Data sources

| Data | Source | Variables |
|---|---|---|
| Gridded predictors | Copernicus Climate Data Store (CDS) | SST, geopotential height, rainfall and air temperature from all seasonal forecast models on the CDS as of July 2026, except UKMO |
| Gridded predictand | CDS, ERA5 reanalysis | rainfall and temperature |
| Teleconnection indices | Japan Meteorological Agency (JMA) | IOD, Niño3, Niño4; JMA is used because it publishes with the shortest delay |
| Gridded predictors *(legacy)* | IRI Data Library (IRIDL) | SST |
| Gridded predictand *(legacy)* | IRIDL | CHIRPS precipitation |
| Gridded forecasts and hindcasts *(legacy)* | IRIDL | SST, precipitation and geopotential height from the three NMME models operational as of August 2025 |

Downloads from IRIDL and JMA need no account. Downloads from the CDS need a free account and an API key, set up once as described below.

## Setting up access to the CDS

### 1. Create an account

Register on the [Climate Data Store](https://cds.climate.copernicus.eu) and log in.

### 2. Copy your API key

Open the [CDS API setup page](https://cds.climate.copernicus.eu/how-to-api) while logged in. It shows your personal access token, a long code of letters and digits.

### 3. Create the `.cdsapirc` file

Create a plain text file named `.cdsapirc` in your home directory, with these two lines. Replace the second line's placeholder with your token:

```
url: https://cds.climate.copernicus.eu/api
key: <PERSONAL-ACCESS-TOKEN>
```

Where the file goes:

| System | Location |
|---|---|
| Linux, macOS | `$HOME/.cdsapirc`, e.g. `/home/username/.cdsapirc` |
| Windows | `%USERPROFILE%\.cdsapirc`, e.g. `C:\Users\username\.cdsapirc` |

On Windows, make sure the file is not saved as `.cdsapirc.txt`. In Notepad, choose **Save as type: All files**.

### 4. Accept the dataset licences

Each CDS dataset has its own terms of use, which must be accepted once, on the dataset's web page, before the API can download it. Open each dataset CFT downloads from on the CDS website. At the bottom of its **Download** tab, accept the licence.

If a download fails with a message about licences or terms of use, a licence still needs to be accepted.

### 5. Check the setup

The `cdsapi` client is installed with CFT. CFT needs version 0.7.7 or later, which you can check with:

```bash
pip show cdsapi
```

The download module will now fetch CDS data without asking for credentials. The key is personal: do not share the `.cdsapirc` file or put it in a shared folder.

## Running without the graphical interface

CDS downloads can be called from Python:

```python
from cft.functions.functions_download import cdsDownloadReanalysis, cdsDownloadForecast
```

See the [API reference](../api.rst) for their arguments.
