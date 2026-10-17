"""
DWTP (dry-to-wet transition period) kernel and helper functions.

Port of the original PxlProcess, FindOnsetPeriods, FindNrRainy, RefineOns, WetDrySpells,
DelCandidate and butterworth functions, working on numpy arrays for one location.
The logic is kept as in the original - nothing is fixed. Issues are marked with "# FLAG:".
Only changes:
    - xarray/cftime date arithmetic replaced by positions in the (no-leap) daily series
    - Butterworth coefficients passed as arguments instead of computed in the function
    - the climatological envelope is derived from the climatological period (climStart:climStop)
      instead of the whole record; with climStart=0, climStop=len(pp) results are identical
    - print('!!!!!CHECK!!!!') in FindNrRainy replaced by a flag returned in status
    - exceptions are caught and reported in status, instead of stopping the run
"""

import itertools as it

import numpy as np
from scipy.signal import filtfilt


NSTATS = ['FirstDay', 'Length', 'OnsIntensity', 'TotPrecip', 'PrecipRate',
          'PrecipInt', 'FrcWetDays', 'LengthWetSpells', 'MaxWetSpell',
          'FrcDryDays', 'LengthDrySpells', 'MaxDrySpell']

# status of the calculation for a location
DWTP_STATUS = {0: "ok", 1: "no dry-to-wet transition periods found", 2: "error",
               3: "ok, but FindNrRainy raised the CHECK warning"}


def onsetDWTP(pp, doy, years, climStart, climStop, b, a, padLen, minlen, mxrainy):
    """
    Kernel for one location (port of PxlProcess).
        pp        - daily rainfall, no-leap (29 Feb removed), 1-D
        doy       - day of year (1-365, no-leap) of each day in pp
        years     - calendar year of each day in pp
        climStart, climStop - positions of the climatological period in pp (start, stop+1);
                    the period should start on 1 January and cover complete years
        b, a, padLen - Butterworth filter coefficients and padding length (2*fwin)
        minlen    - minimum length of transition periods (original: 30)
        mxrainy   - maximum number of climatological envelopes (original: 2)
    Returns:
        ons    - (years, sea, nstats) DWTP statistics, as in the original
        clmEnv - (season, Stats) climatological envelope [FirstDay, Length], as in the original
        w0     - start of water year, day of year (original clm[2])
        flt    - filtered daily rainfall (original bwpp)
        status - see DWTP_STATUS
    """
    vyr = np.unique(years)
    ons = np.full((len(vyr), mxrainy, len(NSTATS)), np.nan)
    clmEnv = np.full((mxrainy, 2), np.nan)
    flt = np.full(len(pp), np.nan)
    try:
        frstEnv, lnt, w0, ons, flt, status = pxlProcess(pp, doy, years, vyr, climStart, climStop,
                                                       b, a, padLen, minlen, mxrainy)
        if status == 1:
            return ons, clmEnv, np.nan, flt, 1.0

        # as in the main script: climEnv.loc[{'season':slice(0,len(clm[0])), ...}] = clm[0]
        # FLAG: label-based slice(0, n) includes n, so with one envelope (n=1) seasons 0 AND 1 are
        #       both set to the values of the single envelope
        n = len(frstEnv)
        clmEnv[0:n + 1, 0] = frstEnv
        clmEnv[0:n + 1, 1] = lnt
    except Exception:
        return (np.full((len(vyr), mxrainy, len(NSTATS)), np.nan), np.full((mxrainy, 2), np.nan),
                np.nan, np.full(len(pp), np.nan), 2.0)
    return ons, clmEnv, float(w0), flt, float(status)


def butterworth(indat, b, a, padLen):
    # port of the original butterworth(); b, a = butter(2, 1/cutoff), padLen = int(2*cutoff)
    # FLAG: 1/cutoff is relative to the Nyquist frequency, so cutoff=60 removes periods shorter
    #       than ~120 days (not 60)
    padd1 = indat[:padLen][::-1]
    padd2 = indat[len(indat) - padLen:][::-1]
    paddannual = np.hstack((padd1, indat, padd2))
    # FLAG: NaNs are removed before filtering, so with missing data the output is shorter than
    #       the input and shifted against the dates (raises an error here -> status 2)
    y = filtfilt(b, a, paddannual[~np.isnan(paddannual)])
    out = y[padLen:-padLen]
    if len(out) != len(indat):
        raise ValueError("missing data in the series")
    return out


def pxlProcess(pp, doy, years, vyr, climStart, climStop, b, a, padLen, minlen, mxrainy):
    ndays = 365
    nstats = NSTATS
    ons = np.full((len(vyr), mxrainy, len(nstats)), np.nan)
    status = 0

    flt = butterworth(pp, b, a, padLen)  # filtering

    # xarray differentiate on a daily series = np.gradient (central differences, one-sided at ends)
    grd = np.gradient(flt)
    rny = np.where(((flt > 0) & (grd > 0)), 1, 0)

    # Climatological envelope - from the climatological period
    ncyr = len(np.unique(years[climStart:climStop]))
    fltClim = flt[climStart:climStop]
    fd, lns = FindOnsetPeriods(rny[climStart:climStop], minlen)

    if (len(fd) > 0):

        # FLAG: FindNrRainy is called with its default minlen=25, while transition periods use minlen=30
        frst, lnt, w0, check = FindNrRainy(fd, lns, ncyr, ndays, mxnr=mxrainy)
        if check:
            status = 3

        # Check the intensity of the precipitation in each envelope if more than one transition
        # Remove envelopes with low precipitation. This can happen in dry areas
        if (len(frst) > 1):
            tmp = np.zeros((ncyr * ndays)); tmp[:] = np.nan
            tmp[:len(fltClim)] = fltClim
            # FLAG: assumes the climatological period starts on 1 January
            tmp = np.nanmean(np.reshape(tmp, (ncyr, ndays)), 0)
            # FLAG: frst+lnt can exceed 365 for an envelope crossing the year end - the slice is then
            #       truncated at 31 December instead of wrapping around
            fave = np.asarray([np.nanmean(tmp[frst[ss]:frst[ss] + lnt[ss]])
                               for ss in range(len(frst))])
            pst = [ii for ii in range(len(frst)) if fave[ii] >= (np.max(fave) * .35)]
            # FLAG: comment in original says 20%, code uses 35%
            # keep envelopes that have at least 20% of the maximum mean precipitation
            if (len(pst) > 0):
                frst = frst[pst]; lnt = lnt[pst]

    else:
        # FLAG: the original returns only two values here, while the main script expects three
        return None, None, None, ons, flt, 1

    last = len(pp) - 1
    dd0 = np.nonzero(doy == w0 + 1)[0]  # w0 in each year (positions)
    t0 = frst - w0; t0[t0 < 0] += ndays  # the climatological envelope starts t0 days after w0
    tf = t0 + lnt

    for yi in dd0:
        # This cycle is from w0 to w0+365, but the onset period is registered
        # to the calendar year.
        for ss in range(len(frst)):
            # skip the last season, if it starts less than 30 days before the end of the time series
            if (yi + t0[ss]) > (last - minlen): break

            # Calendar year of the onset period
            kk = years[yi + t0[ss]]
            k = np.searchsorted(vyr, kk)

            fd, ld = RefineOns(pp[yi + t0[ss]:yi + tf[ss] + 1],
                               np.nanmax(flt[yi:yi + ndays]) * 0.1)

            # First day of the onset period for this year
            # FLAG: here FirstDay = fd+t0+w0 is a 0-based day of year, while in the first-year block
            #       below it is fd+t0+1 (1-based); it also exceeds 365 when the envelope starts in the
            #       next calendar year (wrap-around commented out in the original), although the
            #       year kk is already the next calendar year
            ons[k, ss, 0] = fd + t0[ss] + w0  # DOY
            ons[k, ss, 1] = ld - fd

            if (not np.isnan(fd)):
                s0 = yi + t0[ss] + fd; s1 = yi + t0[ss] + ld
                # Intensity: mean gradient of the BW60 filtered precipitation during the onset period
                ons[k, ss, 2] = np.nanmean(grd[s0:s1 + 1])
                # Total precipitation during the onset period
                ons[k, ss, 3] = np.nansum(pp[s0:s1 + 1])

                win = pp[yi:yi + ndays]
                mask = np.zeros(len(win), dtype=win.dtype)  # same type as data, as xr.zeros_like
                # in case less than one complete year, usually at the end of the time series
                mask[fd + t0[ss]:ld + t0[ss] + 1] = 1
                wet = WetDrySpells(mask, win, (fd + t0[ss], ld - fd))
                ons[k, ss, 4:] = wet
            else:
                ons[k, ss, 2:] = np.nan

    # do first year
    # FLAG: assumes the series starts on 1 January
    if np.any(frst < doy[dd0[0]]):
        pst = (frst < doy[dd0[0]]).nonzero()[0]
        yi = 0  # starting on the first day of the time series
        t0 = frst; tf = t0 + lnt
        for ss in pst:
            kk = years[yi + t0[ss]]
            k = np.searchsorted(vyr, kk)

            fd, ld = RefineOns(pp[yi + t0[ss]:yi + tf[ss] + 1],
                               np.nanmax(flt[yi:yi + ndays]) * 0.1)

            ons[k, ss, 0] = fd + t0[ss] + 1  # DOY
            ons[k, ss, 1] = ld - fd

            if (not np.isnan(fd)):
                s0 = yi + t0[ss] + fd; s1 = yi + t0[ss] + ld
                ons[k, ss, 2] = np.nanmean(grd[s0:s1 + 1])
                ons[k, ss, 3] = np.nansum(pp[s0:s1 + 1])

                win = pp[yi:yi + ndays]
                mask = np.zeros(len(win), dtype=win.dtype)  # same type as data, as xr.zeros_like
                mask[fd + t0[ss]:ld + t0[ss] + 1] = 1
                wet = WetDrySpells(mask, win, (fd + t0[ss], ld - fd))
                ons[k, ss, 4:] = wet
            else:
                ons[k, ss, 2:] = np.nan

    return frst + 1, lnt, w0 + 1, ons, flt, status


def FindOnsetPeriods(indat, minlen):
    '''
        Given an time series of 0's and 1's, this functions locates the
        position and length of sequences of 1's with minimum number of entries
        defined by minlen.
    '''
    ps = 0; lenseason = []; firstday = []
    for key, grp in it.groupby(indat):
        tmp = len(list(grp))
        if key == 0:
            pass
        else:
            if (tmp >= minlen):
                lenseason.append(tmp)
                firstday.append(ps)
        ps = ps + tmp

    return firstday, lenseason


def FindNrRainy(fd, ln, nyrs, ndays, minlen=25, mxnr=False):
    '''
        Identifies the number of rainy seasons and the expected window that it should occur.
        Port of the original; returns also a flag (True if the original would print '!!!!!CHECK!!!!').
    '''
    check = False

    # mask with periods in onset
    tmpmask = np.zeros((nyrs * ndays))
    for ii in range(len(fd)):
        ps = list(range(fd[ii], fd[ii] + ln[ii]))
        tmpmask[ps] = 1

    # FLAG: assumes the series starts on 1 January and has complete years
    tmpmask = np.reshape(tmpmask, (nyrs, ndays))
    pdf = np.nansum(tmpmask, 0)

    pdfN = (pdf - pdf.min()) / (pdf.max() - pdf.min())

    # locating the minimum and shifting the time series to start at this point
    w0 = np.argmin(pdfN)
    if (w0 > 0): pdfN = np.hstack((pdfN[w0:], pdfN[:w0]))

    # smoothing using a running mean
    ws = 14
    padded = np.pad(pdfN, (ws // 2, ws - ws // 2 - 1), mode='edge')
    pdfNS = np.convolve(padded, np.ones((ws,)) / ws, mode='valid')

    # Locating periods with largest frequence of onset (above 0.5)
    pps = [ps for ps in range(ndays - 1) if ((pdfNS[ps] < .5) & (pdfNS[ps + 1] >= .5))]
    nps = [ps for ps in range(ndays - 1) if ((pdfNS[ps] >= .5) & (pdfNS[ps + 1] < .5))]

    if (len(pps) == 0):
        if (pdfNS.max() < 0.5):
            pps = [ps for ps in range(ndays - 1) if ((pdfNS[ps] < 0.5 * pdfNS.max()) &
                                                    (pdfNS[ps + 1] >= 0.5 * pdfNS.max()))]
            nps = [ps for ps in range(ndays - 1) if ((pdfNS[ps] >= 0.5 * pdfNS.max()) &
                                                    (pdfNS[ps + 1] < 0.5 * pdfNS.max()))]
        if (pdfNS.min() > 0.5):
            thr = 0.5 * (pdfNS.max() - pdfNS.min()) + pdfNS.min()
            pps = [ps for ps in range(ndays - 1) if ((pdfNS[ps] < thr) &
                                                    (pdfNS[ps + 1] >= thr))]
            nps = [ps for ps in range(ndays - 1) if ((pdfNS[ps] >= thr) &
                                                    (pdfNS[ps + 1] < thr))]

    # Sanity check point
    if (len(nps) != len(pps)):
        if (len(nps) < len(pps)):
            if (pdfNS[-1] >= 0.5 * pdfNS.max()): nps.append(ndays - 1)
            else: check = True  # FLAG: original prints '!!!!!CHECK!!!!' and continues
        else:
            if (pdfNS[0] >= 0.5 * pdfNS.max()): pps.insert(0, 0)
            else: check = True  # FLAG: original prints '!!!!!CHECK!!!!' and continues
    else:
        # FLAG: raises IndexError if no crossing was found at all (pps and nps empty)
        if (pps[0] > nps[0]): pps.insert(0, 0)
        if (pps[-1] > nps[-1]): nps.append(ndays - 1)

    # merge periods separated by short breaks
    mrg = []
    for ii in range(len(pps) - 1):
        if (pps[ii + 1] - nps[ii] <= 30):  # Arbitrary, check if it is a good size
            if (np.min(pdfNS[nps[ii]:pps[ii + 1] + 1]) > 0.3): mrg.append(ii)

    if (len(mrg) > 0):
        mrg.sort()
        for ii in mrg[::-1]: nps.pop(ii); pps.pop(ii + 1)

    # lower threshold for seasons not present all years (pdfNS.max < 1)
    if ((len(pps) > 1) | (len(nps) > 1)):
        ps = (np.asarray([pdfNS[pps[ii]:nps[ii]].max()
                          for ii in range(len(pps))]) < pdfNS.max()).nonzero()[0]
        if (len(ps) > 0):
            for jj in ps:
                tmp1 = [ii for ii in range(ndays - 1)
                        if ((pdfNS[ii] < .5 * (pdfNS[pps[jj]:nps[jj]].max())) &
                            (pdfNS[ii + 1] >= .5 * (pdfNS[pps[jj]:nps[jj]].max())))]
                tmp2 = [ii for ii in range(ndays - 1)
                        if ((pdfNS[ii] >= .5 * (pdfNS[pps[jj]:nps[jj]].max())) &
                            (pdfNS[ii + 1] < .5 * (pdfNS[pps[jj]:nps[jj]].max())))]
                if (len(tmp2) < len(tmp1)): tmp2.append(ndays - 1)
                if (len(tmp1) < len(tmp2)): tmp1.insert(0, 0)
                if ((len(tmp1) > 0) | (len(tmp2) > 0)):
                    if (tmp1[0] > tmp2[0]): tmp1.insert(0, 0)
                    if (tmp1[-1] > tmp2[-1]): tmp2.append(ndays - 1)

                    kk = np.argmin(abs(pps[jj] - np.asarray(tmp1)))
                    tmp1 = tmp1[kk]; tmp2 = tmp2[kk]
                    keep = True
                    for ii in range(len(pps)):
                        if (ii != jj):
                            if (tmp1 in range(pps[ii], nps[ii])): keep = False
                            if (tmp2 in range(pps[ii], nps[ii])): keep = False
                            if (pps[ii] in range(tmp1, tmp2)): keep = False
                            if (nps[ii] in range(tmp1, tmp2)): keep = False
                    if (keep): pps[jj] = tmp1; nps[jj] = tmp2

    # eliminating periods with less than minlen days
    ln = np.asarray([nps[ii] - pps[ii] + 1 for ii in range(len(pps))])
    if (np.all(ln < minlen)):
        if (ln.max() > .75 * minlen):
            ps = np.argmax(ln)
            pps = [pps[ps]]; nps = [nps[ps]]
    else:
        rmv = (ln < minlen).nonzero()[0]
        if (len(rmv) > 0):
            rmv.sort()
            for ii in rmv[::-1]: pps.pop(ii); nps.pop(ii)

    # If there is a limit to the number of rainy seasons to be considered
    if (not isinstance(mxnr, bool)):
        while (len(pps) > mxnr):
            mx = np.asarray([pdfNS[pps[ii]:nps[ii]].max() for ii in range(len(pps))])
            ii = np.argmin(mx)
            pps.pop(ii); nps.pop(ii)

    # FLAG: envelope length here is nps-pps, while minlen check above uses nps-pps+1
    lnt = np.asarray(nps) - np.asarray(pps)
    frst = np.asarray(pps) + w0
    frst = np.where(frst >= ndays, frst - ndays, frst)
    # sorting according to the first day
    lnt = lnt[np.argsort(frst)]
    frst = frst[np.argsort(frst)]

    return frst, lnt, w0, check


def RefineOns(pp, thrs):
    '''
        Port of the original RefineOns. pp - daily rainfall in the envelope (1-D),
        thrs - 10% of the maximum filtered rainfall in the water year (mm/day)
    '''
    # end of the period: day when the cumulative precipitation reaches 50%
    # of the total precipitation during the onset period envelope
    tot = np.nancumsum(pp)  # xarray cumsum skips NaN
    # FLAG: compares total rainfall (mm) with thrs, which is a daily rate (mm/day)
    if tot.max() < thrs:  # not enough precipitation in the season
        ld = np.nan; fd = np.nan
    else:
        ld = (tot >= 0.5 * tot.max()).nonzero()[0][0].item()

        # Rolling mean - 3 days, centred; NaN at both ends (xarray rolling with min_periods=3)
        pp3 = np.full(len(pp), np.nan)
        if len(pp) >= 3:
            pp3[1:-1] = (pp[:-2] + pp[1:-1] + pp[2:]) / 3

        cnd = np.where(pp3 <= thrs, 1, 0)

        fd1, ln1 = FindOnsetPeriods(cnd, 1)  # Identifying precipitation break periods

        # FLAG: comment in original says longer than 10 days, code uses 12
        vld = (np.asarray(fd1) + np.asarray(ln1) > ld).nonzero()[0]
        if (len(vld) > 0):
            pst = (np.asarray(ln1)[vld] > 12).nonzero()[0]
            if (len(pst) > 0): ld = fd1[vld[pst[-1]]] + ln1[vld[pst[-1]]]

        # removing breaks that happened at the end of the envelope.
        rmv = (np.asarray(fd1) + np.asarray(ln1) >= ld).nonzero()[0]
        fd2, ln2 = DelCandidate(rmv, fd1, ln1)

        if (len(fd2) > 0):
            # FLAG: comment in original says 33%, code uses 30%
            rmv = (tot[fd2] / tot[-1] > 0.3).nonzero()[0]
            fd3, ln3 = DelCandidate(rmv, fd2, ln2)

            # Now locating the longest period of low precipitation
            if (len(ln3) > 0):
                mxl = np.nanmax(np.asarray(ln3))
                mx = (np.asarray(ln3) == mxl).nonzero()[0][-1]  # ties - the latest one
                fd = fd3[mx] + ln3[mx]  # at the end of the maximum period of low precipitation
            elif (len(fd2) > 0):
                mxl = np.nanmax(np.asarray(ln2))
                mx = (np.asarray(ln2) == mxl).nonzero()[0][-1]
                fd = fd2[mx] + ln2[mx]
            else: fd = 0
        else: fd = 0  # no onset period found

    return fd, ld


def WetDrySpells(msk, pp, ons):
    '''
        Port of the original WetDrySpells. msk - mask (1 in the onset period), pp - rainfall in the
        water year, ons - (first day, length) of the onset period. Returns 8 statistics.
        FLAG: docstring of the original defines wet days as PP >= 1 and dry days as PP < 1, but the
              code uses PP > 0 (wet) and PP == 0 (dry)
        FLAG: spells that are only partly inside the onset period are not counted
    '''
    onsStats = np.zeros((8)); onsStats[:] = np.nan

    msk = np.where(msk == 1, msk, np.nan)
    vldpp = pp * msk

    wet = np.where(vldpp > 0, 1., 0)
    dd0 = (np.diff(wet) == 1).nonzero()[0] + 1
    ddf = (np.diff(wet) == -1).nonzero()[0]
    if (wet[0] == 1): dd0 = np.insert(dd0, 0, 0)
    if (wet[-1] == 1): ddf = np.insert(ddf, len(ddf), pp.size - 1)
    wetlen = [(ii, jj, vldpp[int(ii):int(jj) + 1]) for ii, jj in zip(dd0, ddf)]

    # dry days
    dry = np.where(vldpp == 0, 1., 0)
    dd0 = (np.diff(dry) == 1).nonzero()[0] + 1
    ddf = (np.diff(dry) == -1).nonzero()[0]
    if (dry[0] == 1): dd0 = np.insert(dd0, 0, 0)
    if (dry[-1] == 1): ddf = np.insert(ddf, len(ddf), pp.size - 1)
    drylen = [(ii, jj, vldpp[int(ii):int(jj) + 1]) for ii, jj in zip(dd0, ddf)]

    di = ons[0]
    df = di + ons[1]

    # wet spell stats
    vld = [ii for ii in range(len(wetlen)) if ((wetlen[ii][0] >= di) & (wetlen[ii][1] <= df))]
    if (len(vld) > 0):
        totpp = sum([sum(wetlen[ii][2]) for ii in vld])
        nrwet = sum([len(wetlen[ii][2]) for ii in vld])
        onsStats[0] = totpp / ons[1]
        onsStats[1] = totpp / float(nrwet)
        onsStats[2] = 100 * (nrwet / ons[1])
        onsStats[3] = nrwet / float(len(vld))
        onsStats[4] = max([len(wetlen[ii][2]) for ii in vld])
    else: onsStats[:5] = 0.

    # Dry spell stats
    vld = [ii for ii in range(len(drylen)) if ((drylen[ii][0] >= di) & (drylen[ii][1] <= df))]
    if (len(vld) > 0):
        nrdry = sum([len(drylen[ii][2]) for ii in vld])
        onsStats[5] = 100 * (nrdry / ons[1])
        onsStats[6] = nrdry / float(len(vld))
        onsStats[7] = max([len(drylen[ii][2]) for ii in vld])
    else: onsStats[5:] = 0.

    return onsStats


def DelCandidate(rmv, firstday, lenseason):
    fd, ln = firstday.copy(), lenseason.copy()
    if (len(rmv) > 0):
        rmv.sort()
        for ii in rmv[::-1]:
            ln.pop(ii)
            fd.pop(ii)
    return fd, ln
