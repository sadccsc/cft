# functions added by Piotr
import geopandas
from matplotlib import pyplot as plt
import matplotlib.colors as colors
import cartopy.crs as ccrs


def showMessage(_message):
    global window
    window.statusbar.showMessage(_message)
    window.manual_update()
    #    window.logWindow.appendHtml(_message)

def skill_single(_fprob,_obs_terc,_index):
    if _index=="heidke_hits_max":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            #this will be 1,2,3
            #print(_obs_terc[0])
            #print(np.isnan(_obs_terc[0]))
            temp=np.concatenate([_fprob,_obs_terc.reshape(-1,1)], axis=1)
            #this is heidtke hits
            _hits=np.apply_along_axis(get_heidke_hit,1,temp)
            return(_hits)
        else:
            _hits=np.copy(_obs_terc)
            _hits[:]=np.nan
        return(_hits)
        
    if _index=="interest_rate":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            temp=np.concatenate([_fprob,_obs_terc.reshape(-1,1)], axis=1)
            _intrate=np.apply_along_axis(get_interest_rate,1,temp)
            return(_intrate)
        else:
            _intrate=np.copy(_obs_terc)
            _intrate[:]=np.nan
            return(_intrate)        
    if _index=="ignorance":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            #this will be 1,2,3
            temp=np.concatenate([_fprob,_obs_terc.reshape(-1,1)], axis=1)
            _ignorance=np.apply_along_axis(get_ignorance,1,temp)
            return(_ignorance)
        else:
            _ignorance=np.copy(_obs_terc)
            _ignorance[:]=np.nan
            return(_ignorance)

def get_heidke_hit(_x):
    #print(_x)
    mxs=(_x==np.max(_x[0:3])).astype(int)
    #_x[3] is in 1,2,3    
    mxs=mxs[int(_x[3]-1)]*1/np.sum(mxs)
    return mxs


def cemcat_to_tercprob(_cat):
    _cem_probs=np.array([[40,35,25],[35,40,25],[25,40,35],[25,35,40]])/100
    _probs=np.array([_cem_probs[int(x-1)] if not np.isnan(x) else np.array([np.nan,np.nan,np.nan]) for x in _cat])
    return _probs


def val_to_cemcat(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.isnan(_val))==0:
        _q1,_q2,_q3=np.quantile(_obs,[0.33,0.5,0.66])
        _out[_val<=_q1]=1
        _out[(_val>_q1) & (_val<=_q2)]=2
        _out[(_val>_q2) & (_val<=_q3)]=3
        _out[_val>_q3]=4
    return(_out)

def val_to_terc(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.invert(np.isnan(_val)))>0:
        _q1,_q2=np.quantile(_obs,[0.33,0.66])
        _out[_val<=_q1]=1
        _out[(_val>_q1) & (_val<=_q2)]=2
        _out[_val>_q2]=3
    else:
        _out[:]=np.nan
    return(_out.astype(float))

def cemcat_to_tercprob(_cat):
    _cem_probs=np.array([[40,35,25],[35,40,25],[25,40,35],[25,35,40]])/100
    _probs=np.array([_cem_probs[int(x-1)] if not np.isnan(x) else np.array([np.nan,np.nan,np.nan]) for x in _cat])
    return _probs 

def get_interest_rate(_x):
    #_x[3] is in 1,2,3
    _prob=_x[int(_x[3]-1)]
    _intrate=_prob/0.33
    return _intrate

def get_ignorance(_x):
        _prob=_x[int(_x[3]-1)]
        if _prob==0:
            _prob=0.01
        _ign=-np.log2(_prob)
        return _ign
    
def get_cem_hit(_f,_o):
    #_f and _o are cemcat of forecast and observations
    if np.sum(np.invert(np.isnan(_f)))>0:
        _temp=np.copy(_f)
        _temp[:]=0
        _temp[_f==_o]=3 #hit
        _temp[np.abs((_f-_o))==1]=2
        _temp[np.abs((_f-_o))==2]=1
    else:
        _temp=np.copy(_f)
        _temp[:]=np.nan
    return _temp


def get_rpss(_f,_o):
    if np.sum(np.invert(np.isnan(_f)))>0 and np.sum(np.invert(np.isnan(_o)))>0:
        fcst_cumprobs=np.array([[40,75,100],[35,75,100],[25,65,100],[25,60,100]])/100
        obs_cumprobs=np.array([[100,100,100],[0,100,100],[0,100,100],[0,0,100]])/100
        clim_cumprobs=np.array([[33,66,100],[33,66,100],[33,66,100],[33,66,100]])/100
        _fcp=fcst_cumprobs[int(_f-1),:]
        _ocp=obs_cumprobs[int(_o-1),:]
        _ccp=clim_cumprobs[int(_o-1),:]
        _rps=np.sum((_fcp-_ocp)**2)
        _rpss=np.sum((_ccp-_ocp)**2)
        _temp=1-(_rps/_rpss)
        #rpss - 0 for climatological forecast, 1 for perfect forecast
    else:
        _temp=np.copy(_f)
        _temp[:]=np.nan
    return _temp

def val_to_quantanom(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.isnan(_val))==0:
        _val=_val[np.invert(np.isnan(_val))]
        _out=(_obs <= _val).mean().reshape(-1)
    return(_out)

def plot_map(_data,_cmap,_levels,_vmin,_vmax, _title, _cbar_label,_ticklabels, _mask, _filename,_geometryfile):
    global showMessage
#    geometryfile="maps/sadc_continental_boundary.geojson"
#    sadc = geopandas.read_file(geometryfile)
    regions = geopandas.read_file(_geometryfile)
    regions=geopandas.read_file("/work/data/sarcof/gis/maps/SADC/GeoJSON/sadc_countries.geojson")
    fig=plt.figure(figsize=(5,4))
    pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
    if _mask is not None:
        _sign,_val=_mask
        if _sign=="above":
            _data=_data.where(_data<_val)
        else:
            _data=_data.where(_data>_val)
    m=_data.plot(cmap=_cmap, vmin=_vmin,vmax=_vmax, add_colorbar=False)
    
    regions.boundary.plot(ax=pl, linewidth=1, color="0.1")    
    plt.title(_title, fontsize=10)
    ax=fig.add_axes([0.82,0.25,0.02,0.5])
    if _levels is None:
        cbar = fig.colorbar(m, cax=ax, label=_cbar_label)
    else:
        cbar = fig.colorbar(m, cax=ax,ticks=_levels, label=_cbar_label)
    if _ticklabels is not None:
        cbar.ax.set_yticklabels(_ticklabels)
    plt.subplots_adjust(bottom=0.05,top=0.9,right=0.8,left=0.05)
    plt.savefig(_filename, dpi=300)
    showMessage(_filename)
#    plt.show()
    plt.close()
    

def openHelp():
    webbrowser.open('verification_help.html')

    
def zonal_mean(_src,_vctr):
    try:
        affine = _src.rio.transform()
        zonalscore = zonal_stats(_vctr, _src[0,:,:].data, affine=affine, nodata=np.nan)
        zonalscore = pd.DataFrame(zonalscore)
    except:
        _src=_src.reindex(latitude=_src.latitude[::-1])
        affine = _src.rio.transform()
        zonalscore = zonal_stats(_vctr, _src[0,:,:].data, affine=affine, nodata=np.nan)
        zonalscore = pd.DataFrame(zonalscore)
    return(zonalscore)



def plot_zonal_histogram(_data, _title, _filename, _ylabel, _hline, _text, _xticklabels):
    global showMessage
    fig=plt.figure(figsize=(6,4))
    pl=fig.add_subplot(1,1,1)
    plt.title(_title, fontsize=10)
    
    _data.plot.bar()
    
    pl.axhline(_hline, linestyle="--",color="0.7")
    pl.text(0.02,0.98,_text, ha='left', va='top', transform=pl.transAxes)
    pl.set_xlabel("zone")
    pl.set_ylabel(_ylabel)
    pl.set_xticklabels(_xticklabels)
    plt.subplots_adjust(bottom=0.15,top=0.9, right=0.9,left=0.15)
    plt.savefig(_filename, dpi=300)
    showMessage(_filename)
#    plt.show()
    plt.close()
