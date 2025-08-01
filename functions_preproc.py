import gl


def forecast():
    #this is called from launchForecastThread()
    global settingsfile
    global predictordict
    global predictanddict
    global fcstPeriod
    
    print("Starting on:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    gl.window.statusbar.showMessage('preparing inputs')
    
    start_time = time.time()

    gl.config['algorithm'] = None
    if gl.window.PCRcheckBox.isChecked():
        gl.config['algorithm']='PCR'
    if gl.window.CCAcheckBox.isChecked():
        gl.config['algorithm']='CCA'
    if len(gl.config.get('algorithm')) == 0:
        gl.window.statusbar.showMessage("No algorithm set!")
        return None
    
    if gl.window.cumRadio.isChecked():
        gl.config['composition'] = "Sum"
    else:
        gl.config['composition'] = "Average"
        
    if gl.window.period1Radio.isChecked():
        gl.config['fcstPeriodLength'] = '3month'
        gl.config['fcstPeriodStartMonth'] = month_start_season.get(str(gl.window.periodComboBox.currentText()))
    else:
        gl.config['fcstPeriodLength'] = '1month'
        gl.config['fcstPeriodStartMonth'] = gl.window.periodComboBox.currentText()
        
    gl.config['predictorMonth'] = gl.window.predictMonthComboBox.currentText()
    
    gl.config['fcstyear'] = int(gl.window.fcstyearlineEdit.text())
    
    gl.config['zonevector']['ID'] = gl.window.zoneIDcomboBox.currentIndex()
    gl.config['basinbounds']['minlat'] = float(str(gl.window.minlatLineEdit.text()).strip() or -90)
    gl.config['basinbounds']['maxlat'] = float(str(gl.window.maxlatLineEdit.text()).strip() or 90)
    gl.config['basinbounds']['minlon'] = float(str(gl.window.minlonLineEdit.text()).strip() or -180)
    gl.config['basinbounds']['maxlon'] = float(str(gl.window.maxlonLineEdit.text()).strip() or 360)
    
    gl.config['crossValidation'] = int(gl.window.startyearLineEdit.text())
    gl.config['predictandID'] = gl.window.predictandIDcombobox.currentText()

    # check if output directory exists
    if not os.path.exists(gl.config.get('outDir')):
        gl.window.statusbar.showMessage("Output Directory not set!")
        return None

    # Write configuration to settings file
    writeConfigToFile(settingsFileName)

    #
    print('\nCFT', gl.config.get('Version'))
    print('\nForecast:', gl.config.get('fcstyear'), gl.window.periodComboBox.currentText())
    print('Configuration:', os.path.basename(settingsfile))
    print('Output directory:', gl.config.get('outDir'))
    print('Predictand: ')

    for predict in gl.config.get('predictandList'):
        print('\t -', os.path.basename(predict))
    print('Predictand attribute:', gl.config.get('predictandattr'))
    print('Predictor: ')
    for predict in gl.config.get('predictorList'):
        print('\t -', os.path.basename(predict))
    print("Predictor month:", gl.config.get('predictorMonth'))
    print('Algorithm: ')
    for alg in gl.config.get('algorithms'):
        print('\t -', alg)
    print("Number of cores to be used:", cpus)
    #adopted convention is that these are predictand years, not predictor years
    print("Training period:", gl.config.get('trainStartYear'), '-', gl.config.get('trainEndYear'))


    # reading predictand data
    nstations = 0
    if gl.config.get('inputFormat') == 'CSV':
        print("reading predictand from csv file...")
        if len(gl.config.get('predictandList')) != 0:
            missing = gl.config.get('predictandMissingValue')
            if len(str(missing)) == 0: missing = -9999
            input_data = concat_csvs(gl.config.get('predictandList'), missing)
            #sel=input_data["ID"]=="ANTSIRANANA"
            #input_data=input_data[sel]
            #print(input_data)
           
            predictandstaryr = int(np.min(input_data['Year']))
            predictandendyr = int(np.max(input_data['Year']))
            if predictandstaryr > int(gl.config.get('trainStartYear')):
                status = "Predictand data starts in " + str(predictandstaryr) + ", does not cover training period"
                print(status)
                gl.window.statusbar.showMessage(status)
                return
            predictanddict['data'] = input_data
            stations = list(input_data['ID'].unique())
            predictanddict['stations'] = stations
            nstations = len(stations)
            predictanddict['lats'], predictanddict['lons'] = [], []
            for n in range(nstations):
                station_data_all = input_data.loc[input_data['ID'] == stations[n]]
                predictanddict['lats'].append(station_data_all['Lat'].unique()[0])
                predictanddict['lons'].append(station_data_all['Lon'].unique()[0])
            processes = stations
            print('stations:',nstations)
            print('predictors:',len(gl.config.get('predictorList')))
            print('algorithms:', gl.config.get('algorithms'))
            print("predictand start year: ",predictandstaryr)
            print("predictand end year: ",predictandendyr)
        else:
            input_data = None
    elif gl.config.get('inputFormat') == 'NetCDF':
        print("reading predictand from netcdf file...")
        if len(gl.config.get('predictandList')) != 0:
            predictand_data = netcdf_data(gl.config.get('predictandList')[0], param=gl.config.get('predictandattr'))
            yrs = [int(x) for x in predictand_data.times()]
            predictandstaryr = int(str(np.min(yrs))[:4])
            if predictandstaryr > int(gl.config.get('trainStartYear')):
                status = "Predictand data starts in " + str(predictandstaryr) + ", does not cover training period"
                print(status)
                gl.window.statusbar.showMessage(status)
                return
            prs = list(range(len(gl.config.get('predictorList'))))
            als = list(range(len(gl.config.get('algorithms'))))
            rows, cols = predictand_data.shape()
            pixels = [(x, y) for x in range(rows) for y in range(cols)]
            combs = [(st, pr, al) for st in pixels for pr in prs for al in als]
            processes = combs
            print('pixels:',len(pixels))
            print('predictors:',len(prs))
            print('algorithms:',gl.config.get('algorithms'))
            print('---> chunks:', len(combs))


    #these are temporary, will be adjusted leater depending on whether or not forecast is done across year boundary
    predictorEndYr = int(gl.config.get('fcstyear'))
    predictorYr = int(gl.config.get('fcstyear'))
    predictorStartYr = int(gl.config.get('trainStartYear'))
    predictorMonth = str(gl.window.predictMonthComboBox.currentText())
    fcstPeriod = str(gl.window.periodComboBox.currentText())
    predictorMonthIndex = months.index(gl.config.get('predictorMonth'))
    if gl.config.get('fcstPeriodLength', '3month') == '3month':
        #fcstPeriod this should be name of the month. if seasonal forecast - then it is code of season (DJF etc)
        fcstPeriod = season_start_month[gl.config.get('fcstPeriodStartMonth')]
        #index is the pythonic index in sequence of calendar months. so 0 is for January
        fcstPeriodIndex = seasons.index(fcstPeriod)
    else:
        fcstPeriod = gl.config.get('fcstPeriodStartMonth')
        fcstPeriodIndex = months.index(fcstPeriod)



    #reading predictor data
    for predictor in gl.config.get('predictorList'):
        print("predictor",predictor)

        if not os.path.isfile(predictor):
            status="does not exist {}".format(predictor)
            print(status)
            gl.window.statusbar.showMessage(status)
            return

        else:
            predictorName, predictorExt = os.path.splitext(os.path.basename(predictor))
            gl.window.statusbar.showMessage('checking ' + predictorName)
            predictorExt = predictorExt.replace('.', '')
            if predictorExt.lower() in ['nc']: 
                try:
                    predictor_data = netcdf_data(predictor)
                except:
                    status = 'ERROR: error in reading ' + predictorName + ', check format'
                    print(status)
                    gl.window.statusbar.showMessage(status)
                    exit()
            else:
                try:
                    predictor_data = csv_data(predictor, predictorMonth, predictorName.replace(' ', '_'))
                except:
                    status = 'ERROR: error in reading ' + predictorName + ', check format'
                    print(status)
                    gl.window.statusbar.showMessage(status)
                    exit()
            predmon = month_dict.get(predictorMonth.lower(), None)
            param = predictor_data.param
            timearr = predictor_data.times()
            print("predictor data first available date:", timearr[0])
            print("predictor data last available date:", timearr[-1])
            sst = predictor_data.tslice()

            rows, cols = predictor_data.shape()

            #this allows for selecting only predictor data for given month
            predictor_year_arr, predictor_mon_arr = [], []
            for x in timearr:
                tyear = x[:4]
                tmonth = x[4:6]
                if tmonth == predmon:
                    predictor_year_arr.append(int(tyear))
                    predictor_mon_arr.append(x)
            print("predictor years:",predictor_year_arr[0],predictor_year_arr[-1])

            if len(predictor_year_arr) == 0:
                status = "Predictor (" + predictorName + ") does not contain any data for " + predictorMonth
                print(status)
                gl.window.statusbar.showMessage(status)
                return

            print("index of predictor's month",predictorMonthIndex)
            print("index of forecast target (predictand's month)",fcstPeriodIndex)

            #fcstperiodIndex is pythonic index of the first month of the forecast period
            #predictorMonthIndex is pythonic index of the predictor month.
            #if predictorMonthIndex >= fcstPeriodIndex:
            if predictorMonthIndex > fcstPeriodIndex:
                print("predictor month is later than forecast, adjusting predictor period")
                #this happens only if forecast is done across the year boundary, so for forecasts for Jan,Feb,Mar etc. based on predictors from Dec,Nov,Oct,Sept etc.
                # in this case, predictor data have to start a year erlier than predictand data
                predictorStartYr = int(gl.config.get('trainStartYear')) - 1
                predictorEndYr = int(gl.config.get('fcstyear')) - 1
            print("needed predictor years:", predictorStartYr, predictorEndYr)
            
            #year_arr - dates for which predictor data are available, with data for the predictor month
            if int(predictorEndYr) > max(predictor_year_arr):
                print("predictor for year ({}) is needed but it is not available in predictor data. ({}-{})".format(predictorYr,predictor_year_arr[0],predictor_year_arr[-1]))
                return

            #fcstyear is the year of the TARGET season. If forecast is done across the year boundary then it does not have to be available. so the original code is wrong.

            #if int(config.get('fcstyear')) > max(year_arr):
            #    predictorStartYr = config.get('trainStartYear') - 1
            #    predictorEndYr = int(config.get('fcstyear')) - 1
            #    print("fcstyear",config.get('fcstyear'),predictorStartYr,predictorEndYr)
            #    if  int(config.get('fcstyear')) - max(year_arr) > 1:
            #        status = "Predictor ("+param+") for " + predictorMonth + " goes up to " + str(year_arr[-1]) + \
            #            ", cannot be used to forecast " + str(config.get('fcstyear')) + ' ' + fcstPeriod
            #        print(status)
            #        window.statusbar.showMessage(status)
            #        return
            #    if fcstPeriodIndex >= predictorMonthIndex:
            #        status = "Predictor ("+param+") for " + predictorMonth + " goes up to " + str(year_arr[-1]) + \
            #            ", cannot be used to forecast " + str(config.get('fcstyear')) + ' ' + fcstPeriod
            #        print(status)
            #        window.statusbar.showMessage(status)
            #        return


            #this checks forecast year vs. training period
            #this is not a sufficient check, as the non-overlapping period should be long enough to conduct forecast validation, but alas!
            if int(gl.config.get('fcstyear')) <= int(gl.config.get('trainEndYear')):
                status = "Cannot forecast {}  as it is not beyond training period {}-{}".format(predictorYr,gl.config.get('trainStartYear'),gl.config.get('trainEndYear'))
                print(status)
                gl.window.statusbar.showMessage(status)
                return

            if predictorStartYr < predictor_year_arr[0]:
                status = "Predictor ("+param+") data starts in " + str(predictor_year_arr[0]) + \
                    ", definition of training period requires them to start in " + str(predictorStartYr)
                print(status)
                gl.window.statusbar.showMessage(status)
                return

            status = 'predictor data to be used: ' + str(predictorStartYr) + predictorMonth + ' to ' + \
                     str(predictorEndYr) + predictorMonth
            print(status)

            #final predictor years - these correspond to the acutal years from which predictor data are
            predictor_years = list(range(predictorStartYr, predictorEndYr + 1))
            print("Prector years to be used: {}-{}".format(predictorStartYr, predictorEndYr))
            print("predictor years:",predictor_years[0],predictor_years[-1]) 
            if predictor_data.shape() == (0, 0):
                sst_arr = np.zeros((len(predictor_years))) * np.nan
            else:
                sst_arr = np.zeros((len(predictor_years), rows, cols)) * np.nan


            #this picks up data from predictor data array. sst_array has to be aligned with predictand data.
            #predictor_years have to be years in predictor data that will later correspond to predictand years
            #sst_arr is a numpy array, so it is agnostic to what actual year data are from
            for y in range(len(predictor_years)):
                year = predictor_years[y]
                indxyear = predictor_year_arr.index(year)
                vtimearr = predictor_mon_arr[indxyear]
                indxtimearr = timearr.index(vtimearr)
                sst_arr[y] = np.array(sst[indxtimearr])


            #sys.exit()

            predictordict[predictorName] = {}
            predictordict[predictorName]['lats'] = predictor_data.lats
            predictordict[predictorName]['lons'] = predictor_data.lons
            predictordict[predictorName]['param'] = param
            predictordict[predictorName]['predictorMonth'] = predictorMonth
            predictordict[predictorName]['data'] = sst_arr
            #ok, here we might have a problem... these are actual years from which predictor is taken...
            predictordict[predictorName]['predictorStartYr'] = predictorStartYr
            predictordict[predictorName]['predictorEndYr'] = predictorEndYr

            sst_arr, sst = None, None

    # create output directory
    outdir = gl.config.get('outDir') + os.sep + 'Forecast_' + str(gl.config.get('fcstyear')) + \
             '_' + fcstPeriod + os.sep
    os.makedirs(outdir, exist_ok=True)

    #return
    # split inputs into different cores and run the processing functions
    print("\nProcessing...")
    p = Pool(cpus)
    if gl.config.get('inputFormat') == 'CSV':
        func = partial(forecast_station, gl.config, predictordict, predictanddict, fcstPeriod, outdir)
    elif gl.config.get('inputFormat') == 'NetCDF':
        func = partial(nc_unit_split, gl.config, predictordict, fcstPeriod)

    rs = p.imap_unordered(func, processes)
    p.close()
    prevcompleted = 0
    while (True):
        completed = rs._index
        if completed != prevcompleted:
            print("Completed " + str(completed) + " of " + str(len(processes)))
            prevcompleted = completed
        if gl.config.get('inputFormat') == 'CSV':
            status = "Completed processing " + str(completed) + " of " + str(len(processes)) + " stations"
        elif gl.config.get('inputFormat') == 'NetCDF':
            status = "Completed " + str(completed) + " of " + str(len(processes)) + " processes"
        if (completed >= len(processes)): break
        gl.window.statusbar.showMessage(status)
        time.sleep(0.3)

    outs = list(rs)
    outputs = []
    for out in outs:
        if isinstance(out, pd.DataFrame):
            if out.shape[0] > 0:
                outputs.append(out)
    if len(outputs) == 0:
        gl.window.statusbar.showMessage('Skill not enough to produce forecast')
        print('Skill not enough to produce forecast')
    else:
        # Write forecasts to output directory
        forecastsdf = pd.concat(outputs, ignore_index=True)
        gl.window.statusbar.showMessage('Writing Forecast...')
        print('Writing Forecast...')
        forecastdir = outdir + os.sep + "Forecast"
        os.makedirs(forecastdir, exist_ok=True)
        fcstprefix = str(gl.config.get('fcstyear')) + fcstPeriod + '_' + predictorMonth
        colors = gl.config.get('colors', {})
        fcstName = str(gl.config.get('fcstyear')) + fcstPeriod
        if gl.config.get('inputFormat') == 'CSV':
            # write forecast by station or zone
            if len(gl.config.get('zonevector', {}).get('file')) == 0:
                fcstcsvout = forecastdir + os.sep + fcstprefix + '_station_members.csv'
                forecastsdf.to_csv(fcstcsvout, header=True, index=True)
                if int(gl.config.get('PODfilter', 1)) == 1:
                    forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                highskilldf = forecastsdf[forecastsdf.HS.ge(int(gl.config.get('minHSscore', 50)))][['ID', 'Lat', 'Lon', 'HS', 'class']]
                r, _ = highskilldf.shape
                if r > 0:
                    csv = forecastdir + os.sep + fcstprefix + '_station_members_selected.csv'                   
                    forecastsdf[forecastsdf.HS.ge(int(gl.config.get('minHSscore', 50)))].to_csv(csv, header=True, index=True)
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
                    base_mapfile = gl.config.get('plots', {}).get('basemap', '')
                    if not os.path.isfile(base_mapfile):
                        base_mapfile = repr(gl.config.get('plots', {}).get('basemap'))
                    if os.path.isfile(base_mapfile):
                        with open(base_mapfile, "r") as read_file:
                            base_map = geojson.load(read_file)
                    station_forecast_png(fcstprefix, stationclass, base_map, colors, forecastdir, fcstName)
                    gl.window.statusbar.showMessage('Done in '+str(convert(time.time()-start_time)))
                    print('Done in '+str(convert(time.time()-start_time)))
                else:
                    gl.window.statusbar.showMessage('Skill not enough for station forecast')
                    print('Skill not enough for station forecast')
            else:
                if not os.path.isfile(gl.config.get('zonevector', {}).get('file')):
                    gl.window.statusbar.showMessage('Error: Zone vector does not exist, will not write zone forecast')
                    print('Error: Zone vector does not exist, will not write zone forecast')
                else:
                    with open(gl.config.get('zonevector', {}).get('file')) as f:
                            zonejson = geojson.load(f)
                    zoneattrID = gl.config.get('zonevector',{}).get('ID')
                    zoneattr = gl.config.get('zonevector', {}).get('attr')[zoneattrID]
                    forecastsdf["Zone"] = np.nan
                    # --------------
                    for n in range(nstations):
                        station = predictanddict['stations'][n]
                        szone = whichzone(zonejson, predictanddict['lats'][n], predictanddict['lons'][n], zoneattr)
                        forecastsdf.loc[forecastsdf.ID == station, 'Zone'] = szone
                    fcstcsvout = forecastdir + os.sep + fcstprefix + '_zone_members.csv'
                    forecastsdf.to_csv(fcstcsvout, header=True, index=True)

                    # generate zone forecast
                    zonefcstprefix = forecastdir + os.sep + str(gl.config.get('fcstyear')) + fcstPeriod + '_' + predictorMonth
                    if int(gl.config.get('PODfilter', 1)) == 1:
                        forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                    highskilldf = forecastsdf[forecastsdf.HS.ge(int(gl.config.get('minHSscore', 50)))][['HS', 'class', 'Zone']]
                    r, _ = highskilldf.shape
                    if r > 0:
                        csv = forecastdir + os.sep + fcstprefix + '_zone_members_selected.csv'                        
                        forecastsdf[forecastsdf.HS.ge(int(gl.config.get('minHSscore', 50)))].to_csv(csv, header=True, index=True)
                        stationsdf = forecastsdf[forecastsdf.HS.ge(int(gl.config.get('minHSscore', 50)))][['ID', 'Lat', 'Lon', 'HS', 'class']]
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
                        ZoneID = gl.config['zonevector']['attr'][gl.config['zonevector']['ID']]
                        zonepoints = gl.config.get('plots', {}).get('zonepoints', '0')
                        zoneclass.set_index('Zone', inplace=True)
                        write_zone_forecast(zonefcstprefix, zoneclass, zonejson, ZoneID, colors, stationclass, zonepoints,
                                            fcstName)
                        gl.window.statusbar.showMessage('Done in '+str(convert(time.time()-start_time)))
                        print('Done in '+str(convert(time.time()-start_time)))
                    else:
                        gl.window.statusbar.showMessage('Skill not enough for zone forecast')
                        print('Skill not enough for zone forecast')
        elif gl.config.get('inputFormat') == 'NetCDF':
            # Write forecasts to output directory
            if int(gl.config.get('PODfilter', 1)) == 1:
                forecastsdf = forecastsdf[
                    forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
            highskilldf = forecastsdf[forecastsdf.HS.ge(int(gl.config.get('minHSscore', 50)))][
                ['Point', 't1', 't2', 't3', 'fcst', 'HS', 'class']]
            r, _ = highskilldf.shape
            if r > 0:
                stationclass = highskilldf.groupby(['Point']).apply(
                    func=weighted_average_fcst).to_frame(name='WA')
                stationclass[['t1', 't2', 't3', 'fcst', 'HS', 'class']] = pd.DataFrame(
                    stationclass.WA.tolist(),
                    index=stationclass.index)
                stationclass = stationclass.drop(['WA'], axis=1)
                comments = 'predictors:'
                for predict in gl.config.get('predictorList'):
                    comments = comments + ' ' + os.path.basename(predict).replace(' ', '_')
                comments = comments + ', predictand: ' + os.path.basename(
                    gl.config.get('predictandList')[0]).replace(' ', '_')
                comments = comments + ', algorithms:'
                for alg in gl.config.get('algorithms'):
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
                            t1[row, col], t2[row, col], t3[row, col], fcst[row, col], HS[row, col], \
                            fclass[row, col] = \
                                np.ravel(stationclass.loc[[point]])
                        except:
                            pass
                fplot = 100 * (fclass - 1) + HS
                # generate NETCDF
                outfile = fcstjsonout = forecastdir + os.sep + fcstprefix + '_forecast.nc'
                output = Dataset(outfile, 'w', format='NETCDF4')
                title = 'Forecast for ' + str(
                    gl.config.get('fcstyear')) + ' ' + fcstPeriod + ' using ' + \
                                     predictorMonth + ' initial conditions'
                output.description = title
                output.comments = 'Created ' + datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
                output.source = 'SCFTv' + gl.config.get('Version')
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
                initial_date.units = 'days since ' + str(gl.config.get('fcstyear')) + '-' + \
                                     str('{:02d}-'.format(fcstPeriodIndex + 1)) + '01 00:00:00'
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
                qmlfile = gl.config.get('plots', {}).get('fcstqml', 'styles'+os.sep+'fcstplot_new.qml')
                outfcstpng = fcstjsonout = forecastdir + os.sep + fcstprefix + '_forecast.png'
                base_mapfile = Path(gl.config.get('plots', {}).get('basemap', ''))
                plot_forecast_png(predictand_data.lats, predictand_data.lons, fplot, title, qmlfile, base_mapfile, outfcstpng)
                gl.window.statusbar.showMessage('Done in '+str(convert(time.time()-start_time)))
                print('Done in ' + str(convert(time.time() - start_time)))
            else:
                gl.window.statusbar.showMessage('Skill not enough for zone forecast')
                print('Skill not enough for zone forecast')
    print("\nEnd time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


