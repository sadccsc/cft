"""
@author: thembani

Note: this file originally held station/pixel-level forecasting logic (forecast_pixel_unit,
forecast_unit, forecast_station, model_skill, etc.) left over from before the codebase was
split into zoning.py and forecast.py. That logic has been removed here since zoning.py never
used it - only season_months/season_average/season_cumulation are actually needed for zoning.
"""
import numpy as np

# --- constants ---
season_months = {'JFM': ['Jan', 'Feb', 'Mar'], 'FMA': ['Feb', 'Mar', 'Apr'], 'MAM': ['Mar', 'Apr', 'May'],
                 'AMJ': ['Apr', 'May', 'Jun'], 'MJJ': ['May', 'Jun', 'Jul'], 'JJA': ['Jun', 'Jul', 'Aug'],
                 'JAS': ['Jul', 'Aug', 'Sep'], 'ASO': ['Aug', 'Sep', 'Oct'], 'SON': ['Sep', 'Oct', 'Nov'],
                 'OND': ['Oct', 'Nov', 'Dec'], 'NDJ': ['Nov', 'Dec', 'Jan'], 'DJF': ['Dec', 'Jan', 'Feb']}


# --- functions ---

def season_cumulation(dfm, year, season):
        nyear = year + 1
    #try:
        if season == 'JFM':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Jan':'Mar']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Jan':'Mar'].sum(axis=1).astype(float), 1)
        if season == 'FMA':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Feb':'Apr']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Feb':'Apr'].sum(axis=1).astype(float), 1)
        if season == 'MAM':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Mar':'May']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Mar':'May'].sum(axis=1).astype(float), 1)
        if season == 'AMJ':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Apr':'Jun']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Apr':'Jun'].sum(axis=1).astype(float), 1)
        if season == 'MJJ':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'May':'Jul']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'May':'Jul'].sum(axis=1).astype(float), 1)
        if season == 'JJA':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Jun':'Aug']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Jun':'Aug'].sum(axis=1).astype(float), 1)
        if season == 'JAS':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Jul':'Sep']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Jul':'Sep'].sum(axis=1).astype(float), 1)
        if season == 'ASO':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Aug':'Oct']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Aug':'Oct'].sum(axis=1).values, 1)
        if season == 'SON':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Sep':'Nov']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Sep':'Nov'].sum(axis=1).astype(float), 1)
        if season == 'OND':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Oct':'Dec']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Oct':'Dec'].sum(axis=1).astype(float), 1)
        if season == 'NDJ':
            p1 = ~np.isnan(np.ravel(dfm.loc[[year], 'Nov':'Dec']).astype(float)).any()
            p2 = ~np.isnan(np.ravel(dfm.loc[[nyear], 'Jan']).astype(float)).any()
            
            if p1 and p2: 
                aggr=np.round(dfm.loc[[nyear], 'Jan'].values + dfm.loc[[year], 'Nov':'Dec'].sum(axis=1).values,1)
                return aggr 

        if season == 'DJF':
            p1 = ~np.isnan(np.ravel(dfm.loc[[year], 'Dec']).astype(float)).any()
            p2 = ~np.isnan(np.ravel(dfm.loc[[nyear], 'Jan':'Feb']).astype(float)).any()
            if p1 and p2: 
                aggr=np.round(dfm.loc[[year], 'Dec'].values + dfm.loc[[nyear], 'Jan':'Feb'].sum(axis=1).values,1)
                return aggr 
        return
   # except:
        print("could not calculate season accumulation", year, season)
        
        return


def season_average(dfm,year,season):
  nyear=year+1
  try:
    if season=='JFM':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Jan':'Mar']).astype(float)).any(): return np.round(dfm.loc[[year],'Jan':'Mar'].mean(axis=1),1)
    if season=='FMA':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Feb':'Apr']).astype(float)).any(): return np.round(dfm.loc[[year],'Feb':'Apr'].mean(axis=1),1)
    if season=='MAM':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Mar':'May']).astype(float)).any(): return np.round(dfm.loc[[year],'Mar':'May'].mean(axis=1),1)
    if season=='AMJ':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Apr':'Jun']).astype(float)).any(): return np.round(dfm.loc[[year],'Apr':'Jun'].mean(axis=1),1)
    if season=='MJJ':
      if ~np.isnan(np.ravel(dfm.loc[[year],'May':'Jul']).astype(float)).any(): return np.round(dfm.loc[[year],'May':'Jul'].mean(axis=1),1)
    if season=='JJA':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Jun':'Aug']).astype(float)).any(): return np.round(dfm.loc[[year],'Jun':'Aug'].mean(axis=1),1)
    if season=='JAS':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Jul':'Sep']).astype(float)).any(): return np.round(dfm.loc[[year],'Jul':'Sep'].mean(axis=1),1)
    if season=='ASO':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Aug':'Oct']).astype(float)).any(): return np.round(dfm.loc[[year],'Aug':'Oct'].mean(axis=1),1)
    if season=='SON':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Sep':'Nov']).astype(float)).any(): return np.round(dfm.loc[[year],'Sep':'Nov'].mean(axis=1),1)
    if season=='OND':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Oct':'Dec']).astype(float)).any(): return np.round(dfm.loc[[year],'Oct':'Dec'].mean(axis=1),1)
    if season=='NDJ':
        p1=~np.isnan(np.ravel(dfm.loc[[year],'Nov':'Dec']).astype(float)).any()
        p2=~np.isnan(np.ravel(dfm.loc[[nyear],'Jan']).astype(float)).any()
        if p1 and p2: return np.round((dfm.loc[[year],'Nov':'Dec'].sum(axis=1).values+dfm.loc[[nyear],'Jan'].values)/3.,1)
    if season=='DJF':
        p1=~np.isnan(np.ravel(dfm.loc[[year],'Dec']).astype(float)).any()
        p2=~np.isnan(np.ravel(dfm.loc[[nyear],'Jan':'Feb']).astype(float)).any()
        if p1 and p2: return np.round((dfm.loc[[year],'Dec'].values+dfm.loc[[nyear],'Jan':'Feb'].sum(axis=1).values)/3.,1)
    return
  except:
    return
