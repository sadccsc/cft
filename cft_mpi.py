"""
@author: thembani
"""
from mpi4py import MPI
import os, sys, time
from dateutil.relativedelta import relativedelta
from datetime import datetime
from netCDF4 import Dataset
import pandas as pd
import numpy as np
import geojson, json
from functions import *

comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()

# Global Variables
version = '3.1.1'
months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
seasons = ['JFM','FMA','MAM','AMJ','MJJ','JJA','JAS','ASO','SON','OND','NDJ','DJF']
csvheader = 'Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec'
season_months = {'JFM': ['Jan', 'Feb', 'Mar'], 'FMA': ['Feb', 'Mar', 'Apr'], 'MAM': ['Mar', 'Apr', 'May'],
                'AMJ': ['Apr', 'May', 'Jun'], 'MJJ': ['May', 'Jun', 'Jul'], 'JJA': ['Jun', 'Jul', 'Aug'],
                'JAS': ['Jul', 'Aug', 'Sep'], 'ASO': ['Aug', 'Sep', 'Oct'], 'SON': ['Sep', 'Oct', 'Nov'],
                'OND': ['Oct', 'Nov', 'Dec'], 'NDJ': ['Nov', 'Dec', 'Jan'], 'DJF': ['Dec', 'Jan', 'Feb']}

fcstyear = None
settingsfile = 'settings.json'
predictordict = {}
predictanddict = {}
predictanddict['stations'] = []
predictanddict['data'] = None
scriptpath = os.path.dirname(os.path.realpath(__file__))

#
def split_chunks(seq, size):
    return (seq[i::size] for i in range(size))

def concat_csvs(csvs, missing):
    dfs_files = []
    for file in csvs:
        dfs_files.append(pd.read_csv(file, encoding = 'ISO-8859-9'))
    dfs_files = pd.concat((dfs_files), axis=0)
    dfs_files = dfs_files.replace(str(missing), np.nan)
    dfs_files = dfs_files.dropna(how='all')
    dfs_files['ID'] = dfs_files['ID'].apply(rename)
    return dfs_files

def get_parameter(list):
    keys = []
    for key in list:
        keys.append(key)
    ref_keys = ['Y', 'X', 'T','zlev']
    for x in reversed(range(len(keys))):
        if keys[x] not in ref_keys:
            return keys[x]
    return None

if __name__ == "__main__":
    start_time = time.time()
    if len(sys.argv) == 2:
        settingsfile = sys.argv[1]

    try:
        with open(settingsfile, "r") as read_file:
            config = json.load(read_file)
        input = os.path.basename(settingsfile)

    except:
        input = 'Defaults'
        config = {}
        config['Version'] = version
        config['outDir'] = ''
        config['predictorList'] = []
        config['predictandList'] = []
        config['predictandMissingValue'] = -9999
        config['predictandattr'] = 'pre'
        config['fcstPeriodStartMonth'] = 'Oct'
        config['fcstPeriodLength'] = '3month'
        config['trainStartYear'] = 1971
        config['trainEndYear'] = 2000
        config['predictorMonth'] = 'Jul'
        config['PValue'] = 0.05
        config['stepwisePvalue'] = 0.3
        config['minHSscore'] = 50
        config['PODfilter'] = 1
        config['inputFormat'] = "CSV"
        config['composition'] = "Sum"
        config['zonevector'] = {"file": "", "ID": 0, "attr": []}
        config['fcstyear'] = fcstyear
        config['algorithms'] = ['LR']
        config['basinbounds'] = {"minlat": -90, "maxlat": 90, "minlon": -180, "maxlon": 360}
        config['plots'] = {'basemap': 'data\sadc_countries.geojson', 'zonepoints': 1,
                           'fcstqml': scriptpath+os.sep+'styles'+os.sep+'fcstplot_new.qml', 'corrmaps': 1,
                           'corrcsvs': 1, 'regrcsvs': 1, 'fcstgraphs': 1, 'trainingraphs': 1}
        config['colors'] = {'class0': '#ffffff', 'class1': '#d2b48c', 'class2': '#fbff03', 'class3': '#0bfffb',
                            'class4': '#1601fc'}
        print("Default settings loaded.")

    if not os.path.exists(config.get('outDir')):
        print("Output Directory not set!")
        exit(1)

    for file in config.get('predictandList'):
        if not os.path.isfile(file):
            print('Predictand file does not exist:', file)
            exit(1)

    for file in config.get('predictorList'):
        if not os.path.isfile(file):
            print('Predictor file does not exist:', file)
            exit(1)

    if config.get('inputFormat') == 'CSV':
        if len(config.get('predictandList')) != 0:
            missing = config.get('predictandMissingValue')
            if len(str(missing)) == 0: missing = -9999
            for filename in config.get('predictandList'):
                with open(filename) as f:
                    fline = f.readline().rstrip()
                if fline.count(',') < 4:
                    print("Format error in "+os.path.basename(filename)+", check if comma delimited")
                    exit(1)
                if csvheader not in fline:
                    print("Format error, one or more column headers incorrect in " + os.path.basename(filename))
                    exit(1)
                if 'ID' not in fline:
                    print("Format error, station name column header should be labelled as ID in " + os.path.basename(filename))
                    exit(1)
            input_data = concat_csvs(config.get('predictandList'), missing)
            predictanddict['data'] = input_data
            stations = list(input_data['ID'].unique())
            predictanddict['stations'] = stations
            nstations = len(stations)
            predictanddict['lats'], predictanddict['lons'] = [], []
            for n in range(nstations):
                station_data_all = input_data.loc[input_data['ID'] == stations[n]]
                predictanddict['lats'].append(station_data_all['Lat'].unique()[0])
                predictanddict['lons'].append(station_data_all['Lon'].unique()[0])
        else:
            input_data = None
    elif config.get('inputFormat') == 'NetCDF':
        if len(config.get('predictandList')) != 0:
            predictand_data = netcdf_data(config.get('predictandList')[0], param=config.get('predictandattr'))
            rows, cols = predictand_data.shape()

    if len(config.get('algorithms', [])) == 0:
        print('no algorithms defined. exit')
        exit(1)

    if len(config.get('predictorList', [])) == 0:
        print('no predictor files loaded. exit')
        exit(1)


    predictorEndYr = int(config.get('fcstyear'))
    predictorStartYr = int(config.get('trainStartYear'))
    predictorMonth = config.get('predictorMonth', 'Jul')
    predictorMonthIndex = months.index(config.get('predictorMonth'))
    if config.get('fcstPeriodLength', '3month') == '3month':
        fcstPeriod = season_start_month[config.get('fcstPeriodStartMonth')]
        fcstPeriodIndex = seasons.index(fcstPeriod)
    else:
        fcstPeriod = config.get('fcstPeriodStartMonth')
        fcstPeriodIndex = months.index(fcstPeriod)


    # create output directory
    outdir = config.get('outDir') + os.sep + 'Forecast_' + str(config.get('fcstyear')) + '_' + fcstPeriod
    os.makedirs(outdir, exist_ok=True)

    if rank == 0:
        print('\nCFT', config.get('Version'))
        print('\nForecast:', config.get('fcstyear'), fcstPeriod)
        print('Configuration:', input)
        print('Output directory:', config.get('outDir'))
        print('Predictand: ')
        for predict in config.get('predictandList'):
            print('\t -', os.path.basename(predict))
        print('Predictand attribute:', config.get('predictandattr'))
        print('Predictor: ')
        for predict in config.get('predictorList'):
            print('\t -', os.path.basename(predict))
        print("Predictor month:", predictorMonth)
        print('Algorithm: ')
        for alg in config.get('algorithms'):
            print('\t -', alg)
        print("Training period:", config.get('trainStartYear'), '-', config.get('trainEndYear'))
        print("number of cores available:", size)
        prs = list(range(len(config.get('predictorList'))))
        als = list(range(len(config.get('algorithms'))))
        if config.get('inputFormat') == 'CSV':
            combs = [(st, pr, al) for st in list(range(nstations)) for pr in prs for al in als]
            chunks = list(split_chunks(combs, size))[::-1]
            print('stations:',nstations,'predictors:',len(prs),'algorithms:',config.get('algorithms'),'---> chunks:',len(combs))
        elif config.get('inputFormat') == 'NetCDF':
            pixels = [(x, y) for x in range(rows) for y in range(cols)]
            combs = [(st, pr, al) for st in pixels for pr in prs for al in als]
            chunks = list(split_chunks(combs, size))[::-1]
            print('pixels:',len(pixels),'predictors:',len(prs),'algorithms:',config.get('algorithms'),'---> chunks:',len(combs))
        print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("\nProcessing...")
    else:
        chunks = None

    # scatter chunks between ranks
    chunks = comm.scatter(chunks, root=0)

    args = []
    for comb in chunks:
        st, pr, alg = comb
        algorithm = config.get('algorithms')[alg]
        predictor = config.get('predictorList')[pr]
        predictorName, predictorExt = os.path.splitext(os.path.basename(predictor))
        print('rank', rank, '|', st, '|', predictorName, '|', algorithm)
        predictordict['Name'] = predictorName
        predictorExt = predictorExt.replace('.', '')
        if predictorExt.lower() in ['nc']: 
            try:
                predictor_data = netcdf_data(predictor)
            except:
                status = 'error in reading ' + predictorName + ', check format'
                print(status)
                exit()
        else:
            try:
                predictor_data = csv_data(predictor, predictorMonth, predictorName.replace(' ', '_'))
            except:
                status = 'error in reading ' + predictorName + ', check format'
                print(status)
                exit()
        predmon = month_dict.get(predictorMonth.lower(), None)
        param = predictor_data.param
        timearr = predictor_data.times()
        sst = predictor_data.tslice()
        predictordict['lats'] = predictor_data.lats
        predictordict['lons'] = predictor_data.lons
        rows, cols = predictor_data.shape()
        year_arr, mon_arr = [], []
        for x in timearr:
            tyear = x[:4]
            tmonth = x[4:6]
            if tmonth == predmon:
                year_arr.append(int(tyear))
                mon_arr.append(x)

        if len(year_arr) == 0:
            print("Predictor ("+param+") does not contain any data for ", predictorMonth)
            continue

        if predictorMonthIndex >= fcstPeriodIndex:
            predictorStartYr = int(config.get('trainStartYear')) - 1
            predictorEndYr = int(config.get('fcstyear')) - 1

        if int(config.get('fcstyear')) > max(year_arr):
            predictorStartYr = config.get('trainStartYear') - 1
            predictorEndYr = int(config.get('fcstyear')) - 1
            if int(config.get('fcstyear')) - max(year_arr) > 1:
                status = "Predictor ("+param+") for " + predictorMonth + " goes up to " + str(year_arr[-1]) + \
                    ", cannot be used to forecast " + str(config.get('fcstyear')) + ' ' + fcstPeriod
                print(status)
                continue
            if fcstPeriodIndex >= predictorMonthIndex:
                status = "Predictor ("+param+") for " + predictorMonth + " goes up to " + str(year_arr[-1]) + \
                    ", cannot be used to forecast " + str(config.get('fcstyear')) + ' ' + fcstPeriod
                print(status)
                continue

        if int(config.get('fcstyear')) <= int(config.get('trainEndYear')):
            status = "Cannot forecast " + str(config.get('fcstyear')) + " as it is not beyond training period"
            print(status)
            continue

        if predictorStartYr < year_arr[0]:
            status = "Predictor ("+param+") data starts in " + str(year_arr[0]) + \
                ", selected options require predictor to start in " + str(predictorStartYr)
            print(status)
            continue
        predictor_years = list(range(predictorStartYr, predictorEndYr + 1))
        if predictor_data.shape() == (0, 0):
            sst_arr = np.zeros((len(predictor_years))) * np.nan
        else:
            sst_arr = np.zeros((len(predictor_years), rows, cols)) * np.nan
        for y in range(len(predictor_years)):
            year = predictor_years[y]
            indxyear = year_arr.index(year)
            vtimearr = mon_arr[indxyear]
            indxtimearr = timearr.index(vtimearr)
            sst_arr[y] = np.array(sst[indxtimearr])

        predictordict['param'] = param
        predictordict['predictorMonth'] = predictorMonth
        predictordict['data'] = sst_arr
        predictordict['predictorStartYr'] = predictorStartYr
        predictordict['predictorEndYr'] = predictorEndYr
        sst_arr, sst = None, None

        if config.get('inputFormat') == 'CSV':
            station = predictanddict.get('stations')[st]
            fcst_unit = forecast_unit(config, predictordict, predictanddict, fcstPeriod, algorithm, station, outdir)
            if fcst_unit is not None:
                args.append(fcst_unit)
        if config.get('inputFormat') == 'NetCDF':
            fcst_unit = forecast_pixel_unit(config, predictordict, predictand_data, fcstPeriod, algorithm, st)
            if fcst_unit is not None:
                args.append(fcst_unit)

        if config.get('inputFormat') == 'NetCDF':
            args.append(comb)

    # receive data from ranks
    recvdata = comm.gather(args, root=0)

    outputs = []
    if rank == 0:
        print("\n")
        forecastdir = outdir + os.sep + "Forecast"
        fcstprefix = str(config.get('fcstyear')) + fcstPeriod + '_' + predictorMonth
        os.makedirs(forecastdir, exist_ok=True)
        if config.get('inputFormat') == 'CSV':
            for xx in range(size):
                rec = recvdata[xx]
                for yy in rec:
                    if isinstance(yy, pd.DataFrame):
                        if yy.shape[0] > 0:
                            outputs.append(yy)
            if len(outputs) == 0:
                print('Skill not enough to produce forecast')
            else:
                # Write forecasts to output directory
                forecastsdf = pd.concat(outputs, ignore_index=True)
                print('Writing Forecast...')
                colors = config.get('colors', {})
                fcstName = str(config.get('fcstyear')) + fcstPeriod
                # write forecast by station or zone
                if len(config.get('zonevector', {}).get('file')) == 0:
                    fcstcsvout = forecastdir + os.sep + fcstprefix + '_station_members.csv'
                    forecastsdf.to_csv(fcstcsvout, header=True, index=True)
                    if int(config.get('PODfilter', 1)) == 1:
                        forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                    highskilldf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['ID', 'Lat', 'Lon', 'HS', 'class']]
                    r, _ = highskilldf.shape
                    if r > 0:
                        csv = forecastdir + os.sep + fcstprefix + '_station_members_selected.csv'                   
                        forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))].to_csv(csv, header=True, index=True)
                        stationclass = highskilldf.groupby(['ID', 'Lat', 'Lon']).apply(func=weighted_average).to_frame(name='WA')
                        stationclass[['wavg', 'class4', 'class3', 'class2', 'class1']] = pd.DataFrame(stationclass.WA.tolist(), index=stationclass.index)
                        stationclass = stationclass.drop(['WA'], axis=1)
                        stationclass['class'] = (stationclass['wavg']+0.5).astype(int)
                        stationclass = stationclass.reset_index()
                        stationclass['avgHS'] = stationclass.apply(lambda x: get_mean_HS(highskilldf, x.ID, 'ID'), axis=1)
                        stationclassout = forecastdir + os.sep + fcstprefix + '_station-forecast.csv'
                        stationclass.to_csv(stationclassout, header=True, index=True)
                        fcstjsonout = forecastdir + os.sep + fcstprefix + '_station-forecast.geojson'
                        data2geojson(stationclass, fcstjsonout)
                        base_map = None
                        base_mapfile = config.get('plots', {}).get('basemap', '')
                        if not os.path.isfile(base_mapfile):
                            base_mapfile = repr(config.get('plots', {}).get('basemap'))
                        if os.path.isfile(base_mapfile):
                            with open(base_mapfile, "r") as read_file:
                                base_map = geojson.load(read_file)
                        station_forecast_png(fcstprefix, stationclass, base_map, colors, forecastdir, fcstName)
                        print('Done in '+str(convert(time.time()-start_time)))
                    else:
                        print('Skill not enough for station forecast')
                else:
                    if not os.path.isfile(config.get('zonevector', {}).get('file')):
                        print('Error: Zone vector does not exist, will not write zone forecast')
                    else:
                        with open(config.get('zonevector', {}).get('file')) as f:
                                zonejson = geojson.load(f)
                        zoneattrID = config.get('zonevector',{}).get('ID')
                        zoneattr = config.get('zonevector', {}).get('attr')[zoneattrID]
                        forecastsdf["Zone"] = np.nan
                        # --------------
                        for n in range(nstations):
                            station = predictanddict['stations'][n]
                            szone = whichzone(zonejson, predictanddict['lats'][n], predictanddict['lons'][n], zoneattr)
                            forecastsdf.loc[forecastsdf.ID == station, 'Zone'] = szone
                        fcstcsvout = forecastdir + os.sep + fcstprefix + '_zone_members.csv'
                        forecastsdf.to_csv(fcstcsvout, header=True, index=True)

                        # generate zone forecast
                        zonefcstprefix = forecastdir + os.sep + str(config.get('fcstyear')) + fcstPeriod + '_' + predictorMonth
                        if int(config.get('PODfilter', 1)) == 1:
                            forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                        highskilldf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['HS', 'class', 'Zone']]
                        r, _ = highskilldf.shape
                        if r > 0:
                            csv = forecastdir + os.sep + fcstprefix + '_zone_members_selected.csv'                        
                            forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))].to_csv(csv, header=True, index=True)
                            stationsdf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['ID', 'Lat', 'Lon', 'HS', 'class']]
                            stationclass = stationsdf.groupby(['ID', 'Lat', 'Lon']).apply(func=weighted_average).to_frame(
                                name='WA')
                            stationclass[['wavg', 'class4', 'class3', 'class2', 'class1']] = pd.DataFrame(
                                stationclass.WA.tolist(), index=stationclass.index)
                            stationclass = stationclass.drop(['WA'], axis=1)
                            stationclass['class'] = (stationclass['wavg']+0.5).astype(int)
                            stationclass = stationclass.reset_index()
                            stationclass['avgHS'] = stationclass.apply(lambda x: get_mean_HS(stationsdf, x.ID, 'ID'), axis=1)
                            zoneclass = highskilldf.groupby('Zone').apply(func=weighted_average).to_frame(name='WA')
                            zoneclass[['wavg', 'class4', 'class3', 'class2', 'class1']] = pd.DataFrame(zoneclass.WA.tolist(), index=zoneclass.index)
                            zoneclass = zoneclass.drop(['WA'], axis=1)
                            zoneclass['class'] = (zoneclass['wavg']+0.5).astype(int)
                            zoneclass = zoneclass.reset_index()
                            zoneclass['avgHS'] = zoneclass.apply(lambda x: get_mean_HS(highskilldf, x.Zone, 'Zone'), axis=1)
                            ZoneID = config['zonevector']['attr'][config['zonevector']['ID']]
                            zonepoints = config.get('plots', {}).get('zonepoints', '0')
                            zoneclass.set_index('Zone', inplace=True)
                            write_zone_forecast(zonefcstprefix, zoneclass, zonejson, ZoneID, colors, stationclass, zonepoints,
                                                fcstName)
                            print('Done in '+str(convert(time.time()-start_time)))
                        else:
                            print('Skill not enough for zone forecast')
        elif config.get('inputFormat') == 'NetCDF':
            for xx in range(size):
                rec = recvdata[xx]
                for yy in rec:
                    if isinstance(yy, pd.DataFrame):
                        if yy.shape[0] > 0:
                            outputs.append(yy)
            if len(outputs) == 0:
                print('Skill not enough to produce forecast')
            else:
                # Write forecasts to output directory
                print('Writing Forecast...')
                forecastsdf = pd.concat(outputs, ignore_index=True)
                if int(config.get('PODfilter', 1)) == 1:
                    forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                highskilldf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['Point', 't1', 't2', 't3', 'fcst', 'HS', 'class']]
                stationclass = highskilldf.groupby(['Point']).apply(func=weighted_average_fcst).to_frame(name='WA')
                stationclass[['t1', 't2', 't3', 'fcst', 'HS', 'class']] = pd.DataFrame(stationclass.WA.tolist(),
                                                                                              index=stationclass.index)
                stationclass = stationclass.drop(['WA'], axis=1)
                comments = 'predictors:'
                for predict in config.get('predictorList'):
                    comments = comments + ' ' + os.path.basename(predict).replace(' ', '_')
                comments = comments + ', predictand: ' + os.path.basename(config.get('predictandList')[0]).replace(' ', '_')
                comments = comments + ', algorithms:'
                for alg in config.get('algorithms'):
                    comments = comments + ' ' + os.path.basename(alg).replace(' ', '_')
                # write outputs to NetCDF
                rows, cols = predictand_data.shape()
                fclass = np.zeros(shape=predictand_data.shape())
                HS = np.ones(shape=predictand_data.shape()) * np.nan
                fcst = np.ones(shape=predictand_data.shape()) * np.nan
                t3 = np.ones(shape=predictand_data.shape()) * np.nan
                t2 = np.ones(shape=predictand_data.shape()) * np.nan
                t1 = np.ones(shape=predictand_data.shape()) * np.nan
                for row in range(rows):
                    for col in range(cols):
                        point = (row, col)
                        try:
                            t1[row, col], t2[row, col], t3[row, col], fcst[row, col], HS[row, col], fclass[row, col] = \
                                np.ravel(stationclass.loc[[point]])
                        except:
                            pass
                fplot = 100 * (fclass - 1) + HS
                # generate NETCDF
                outfile = fcstjsonout = forecastdir + os.sep + fcstprefix + '_forecast.nc'
                output = Dataset(outfile, 'w', format='NETCDF4')
                title = 'Forecast for ' + str(config.get('fcstyear')) + ' ' + fcstPeriod + ' using ' + \
                                     predictorMonth + ' initial conditions'
                output.description = title
                output.comments = 'Created ' + datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
                output.source = config.get('Version')
                output.history = comments
                lat = output.createDimension('lat', rows)
                lon = output.createDimension('lon', cols)
                T = output.createDimension('T', 1)

                initial_date = output.createVariable('target', np.float64, ('T',))
                latitudes = output.createVariable('lat', np.float32, ('lat',))
                longitudes = output.createVariable('lon', np.float32, ('lon',))
                fcstclass = output.createVariable('class', np.uint8, ('T', 'lat', 'lon'))
                hitscore = output.createVariable('hitscore', np.uint8, ('T', 'lat', 'lon'))
                forecast = output.createVariable('forecast', np.uint16, ('T', 'lat', 'lon'))
                tercile3 = output.createVariable('tercile3', np.uint16, ('T', 'lat', 'lon'))
                tercile2 = output.createVariable('tercile2', np.uint16, ('T', 'lat', 'lon'))
                tercile1 = output.createVariable('tercile1', np.uint16, ('T', 'lat', 'lon'))
                fcstplot = output.createVariable('fcstplot', np.uint16, ('T', 'lat', 'lon'))

                latitudes.units = 'degree_north'
                latitudes.axis = 'Y'
                latitudes.long_name = 'Latitude'
                latitudes.standard_name = 'Latitude'
                longitudes.units = 'degree_east'
                longitudes.axis = 'X'
                longitudes.long_name = 'Longitude'
                longitudes.standard_name = 'Longitude'
                initial_date.units = 'days since ' + str(config.get('fcstyear')) + '-' + \
                                     str('{:02d}-'.format(fcstPeriodIndex+1))+'01 00:00:00'
                initial_date.axis = 'T'
                initial_date.calendar = 'standard'
                initial_date.standard_name = 'time'
                initial_date.long_name = 'forecast start date'

                latitudes[:] = predictand_data.lats
                longitudes[:] = predictand_data.lons
                fcstclass[:] = fclass
                hitscore[:] = HS
                forecast[:] = fcst
                tercile3[:] = t3
                tercile2[:] = t2
                tercile1[:] = t1
                fcstplot[:] = fplot
                fcstclass.units = '1=BN, 2=NB, 3=NA, 4=AN'
                fcstplot.units = '100 * (fcstclass - 1) + hitscore'
                hitscore.units = '%'
                output.close()
                qmlfile = config.get('plots', {}).get('fcstqml', scriptpath+os.sep+'styles'+os.sep+'fcstplot_new.qml')
                outfcstpng = fcstjsonout = forecastdir + os.sep + fcstprefix + '_forecast.png'
                base_mapfile = Path(config.get('plots', {}).get('basemap', ''))
                plot_forecast_png(predictand_data.lats, predictand_data.lons, fplot, title, qmlfile, base_mapfile, outfcstpng)
                print('Done in ' + str(convert(time.time() - start_time)))
        print("\nEnd time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
