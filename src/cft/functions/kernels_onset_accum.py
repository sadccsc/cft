"""
Accumulated onset kernels - plain numpy.
Kernel takes x - daily rainfall (1-D numpy array) for one location and one water year, starting
on the start of the water year, and the mean daily rainfall rm.
"""

import numpy as np
from scipy.signal import filtfilt

# order of values returned by accumOnsetDemise
ACCUM_VARS = ["onset", "demise", "wet", "preOnset", "postDemise"]

def butterworthSmooth(x, b, a, padLen):
    # same as the original butterworth(): mirror-padding of padLen (2*cutoff) values at both ends,
    # zero-phase filter with coefficients b, a
    padded = np.concatenate((x[:padLen][::-1], x, x[-padLen:][::-1]))
    return filtfilt(b, a, padded)[padLen:-padLen]
 
 
def onsetAccum(x, rm, onsetDays, demiseDays, b, a, padLen):
    """
    onset, demise, duration and wet/dry season rainfall from anomalous accumulation (Liebmann and Marengo);
    start of the water year from harmonic analysis of the annual cycle (Dunning et al. 2016)
    """
    #"""
    #Kernel. x - daily rainfall for one water year (1-D), rm - mean daily rainfall.
    #b, a, padLen - Butterworth filter coefficients and padding length, from calcAccumOnset.
    #Returns [onset, demise, wet, preOnset, postDemise]:
    #    onset, demise - index of the day in the window (0 = start of water year)
    #    wet - rainfall from onset to demise (both days included)
    #    preOnset - rainfall from start of window to the day before onset
    #    postDemise - rainfall from the day after demise to end of window
    #All NaN if the window has missing data.
    #"""
    
    out = np.full(len(ACCUM_VARS), np.nan)
    if np.isnan(x).any() or np.isnan(rm):
        return out
    anom = x - rm
 
    # onset - minimum of smoothed cumulative anomaly, accumulated forward from start of window
    onset = int(np.argmin(butterworthSmooth(np.cumsum(anom[:onsetDays]), b, a, padLen)))
 
    # demise - minimum of smoothed cumulative anomaly, accumulated backward from end of window
    tail = anom[len(x) - demiseDays:][::-1]
    demise = len(x) - 1 - int(np.argmin(butterworthSmooth(np.cumsum(tail), b, a, padLen)))
 
    out[:] = [onset, demise, x[onset:demise + 1].sum(), x[:onset].sum(), x[demise + 1:].sum()]
    return out
 


def onsetAccum1(x, rm, onsetDays, demiseDays, b, a, padLen):
    """
    Kernel. x - daily rainfall for one water year (1-D), rm - mean daily rainfall.
    b, a, padLen - Butterworth filter coefficients and padding length, from calcAccumOnset.
    Returns [onset, demise, wet, preOnset, postDemise]:
        onset, demise - index of the day in the window (0 = start of water year);
                        -99 if the minimum falls on the first or last day of the search period,
                        i.e. there is no turning point within it (e.g. rains have not started
                        by the end of the onset search)
        wet - rainfall from onset to demise (both days included); NaN if onset or demise is -99
        preOnset - rainfall from start of window to the day before onset; NaN if onset is -99
        postDemise - rainfall from the day after demise to end of window; NaN if demise is -99
    All NaN if the window has missing data.
    """
    out = np.full(len(ACCUM_VARS), np.nan)
    if np.isnan(x).any() or np.isnan(rm):
        return out
    anom = x - rm
 
    # onset - minimum of smoothed cumulative anomaly, accumulated forward from start of window
    i = int(np.argmin(butterworthSmooth(np.cumsum(anom[:onsetDays]), b, a, padLen)))
    onset = i if 0 < i < onsetDays - 1 else -99
 
    # demise - minimum of smoothed cumulative anomaly, accumulated backward from end of window
    tail = anom[len(x) - demiseDays:][::-1]
    k = int(np.argmin(butterworthSmooth(np.cumsum(tail), b, a, padLen)))
    demise = len(x) - 1 - k if 0 < k < demiseDays - 1 else -99
 
    out[0], out[1] = onset, demise
    if onset >= 0:
        out[3] = x[:onset].sum()
    if demise >= 0:
        out[4] = x[demise + 1:].sum()
    if onset >= 0 and demise >= 0:
        out[2] = x[onset:demise + 1].sum()
    return out
