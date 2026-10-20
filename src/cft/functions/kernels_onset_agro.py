"""
Agronomic onset kernels - all in plain numpy as datetime decorator is not passed

Each kernel takes x - daily rainfall (1-D numpy array) for one location and one
season, starting on the season anchor date (first day of the dry season) - and returns:
    index of the onset day, counted from the anchor (0 = anchor day)
    -99 if no onset was found in the season
    NaN if the season has missing data

Onset day is the day on which the accumulation threshold is reached, i.e. the
last day of the accumulation window.
"""

import numpy as np

def trailingSum(x, n):
    # sum over the current and n-1 preceding days. The first n-1 values are partial sums.
    return np.convolve(x, np.ones(n))[:len(x)]


def longestDrySpell(x, thresh=1):
    longest, run = 0, 0
    for value in x:
        run = run + 1 if value < thresh else 0
        longest = max(longest, run)
    return longest


def onsetA(x):
    # 25 mm of accumulated rainfall in 10 days - Tadross 2007
    if np.isnan(x).any():
        return np.nan
    hits = np.where(trailingSum(x, 10) >= 25)[0]
    return float(hits[0]) if len(hits) > 0 else -99.0


def onsetB(x):
    # 25 mm of accumulated rainfall in 10 days, not followed by a period of
    # 10 consecutive days with rainfall < 1 mm in the following 20 days
    if np.isnan(x).any():
        return np.nan
    for i in np.where(trailingSum(x, 10) >= 25)[0]:
        if i + 21 <= len(x) and longestDrySpell(x[i + 1:i + 21]) < 10:
            return float(i)
    return -99.0


def onsetC(x):
    # 45 mm of accumulated rainfall in 4 days
    if np.isnan(x).any():
        return np.nan
    hits = np.where(trailingSum(x, 4) >= 45)[0]
    return float(hits[0]) if len(hits) > 0 else -99.0


def onsetD(x):
    # 20 mm of accumulated rainfall in 3 days, not followed by
    # 10 consecutive days with rainfall < 1 mm in the following 10 days
    if np.isnan(x).any():
        return np.nan
    for i in np.where(trailingSum(x, 3) >= 20)[0]:
        if i + 11 <= len(x) and longestDrySpell(x[i + 1:i + 11]) < 10:
            return float(i)
    return -99.0

def onsetE(x):
    # Sivakumar (1988)
    # 20 mm of accumulated rainfall in 3 days, not followed by a period of
    # 7 consecutive days with rainfall < 1 mm in the following 30 days
    if np.isnan(x).any():
        return np.nan
    for i in np.where(trailingSum(x, 3) >= 20)[0]:
        if i + 31 <= len(x) and longestDrySpell(x[i + 1:i + 31]) < 7:
            return float(i)
    return -99.0

def onsetF(x):
    # Sivakumar (1988)
    # 20 mm of accumulated rainfall in 3 days, not followed by a period of
    # 7 consecutive days with rainfall < 1 mm in the following 30 days
    if np.isnan(x).any():
        return np.nan
    for i in np.where(trailingSum(x, 3) >= 20)[0]:
        if i + 31 <= len(x) and longestDrySpell(x[i + 1:i + 31]) < 7:
            return float(i)
    return -99.0


"""
Rainy-season onset functions, one per country (CFT onset survey, Oct 2026).

Conventions (same as onsetB):
  x       1-D array of daily rainfall (mm) for one location and one season,
          starting on the country's earliest allowed onset date
          (e.g. 1 October for Lesotho and Zimbabwe, 20 September for Zambia).
  return  index (into x) of the day on which the accumulation criterion is
          first met and the false-start check passes;
          np.nan if x contains missing values;
          -99.0 if no onset is found.
  The returned index is the LAST day of the accumulation window, as in onsetB.
  Dry day = rainfall < 1 mm unless the country specifies otherwise.
"""



# ---------------------------------------------------------------- helpers
def trailingSum(x, n):
    """Sum of x over the n days ending on each day; first n-1 values are NaN."""
    x = np.asarray(x, dtype=float)
    out = np.full(x.shape, np.nan)
    if len(x) >= n:
        c = np.concatenate(([0.0], np.cumsum(x)))
        out[n - 1:] = c[n:] - c[:-n]
    return out


def trailingCount(x, n, thresh=1.0):
    """Number of wet days (>= thresh) in the n days ending on each day."""
    return trailingSum((np.asarray(x) >= thresh).astype(float), n)


def longestDrySpell(x, thresh=1.0):
    """Length of the longest run of consecutive days with rainfall < thresh."""
    longest = run = 0
    for v in x:
        run = run + 1 if v < thresh else 0
        longest = max(longest, run)
    return longest


def _hits(s, thresh, strict=False):
    """Indices where the trailing sum s meets the threshold (NaN-safe)."""
    with np.errstate(invalid="ignore"):
        return np.where(s > thresh if strict else s >= thresh)[0]

# ---------------------------------------------------------- country functions
def onsetTadross(x):
    """at least 25 mm of accumulated rainfall in 10 days, with no check for
    a following dry spell (Tadross et al.)"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 10), 25):
        return float(i)
    return -99.0


def onsetAngola(x):
    """at least 25 mm of accumulated rainfall in 10 days, followed by at least
    20 mm of accumulated rainfall in the following 20 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 10), 25):
        if i + 21 <= len(x) and np.sum(x[i + 1:i + 21]) >= 20:
            return float(i)
    return -99.0
 


def onsetBotswana(x):
    """at least 20 mm of accumulated rainfall in 3 days, not followed by a period
    of 7 consecutive days with rainfall < 1 mm in the following 30 days
    (Sivakumar 1988)"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 3), 20):
        if i + 31 <= len(x) and longestDrySpell(x[i + 1:i + 31]) < 7:
            return float(i)
    return -99.0


def onsetEswatini(x):
    """at least 20 mm of accumulated rainfall in 3 days, with no check for a
    following dry spell"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 3), 20):
        return float(i)
    return -99.0


def onsetLesotho(x):
    """more than 25 mm of accumulated rainfall in 5 days, not followed by a period
    of 10 consecutive days with rainfall < 1 mm in the following 21 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 5), 25, strict=True):
        if i + 22 <= len(x) and longestDrySpell(x[i + 1:i + 22]) < 10:
            return float(i)
    return -99.0


def onsetMadagascar(x):
    """at least 20 mm of accumulated rainfall in 2 days, not followed by a period
    of more than 10 consecutive days with rainfall < 1 mm in the following 30 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 2), 20):
        if i + 31 <= len(x) and longestDrySpell(x[i + 1:i + 31]) <= 10:
            return float(i)
    return -99.0


def onsetMalawi(x):
    """at least 25 mm of accumulated rainfall in 3 days, not followed by a period
    of 10 consecutive days with rainfall < 1 mm in the following 21 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 3), 25):
        if i + 22 <= len(x) and longestDrySpell(x[i + 1:i + 22]) < 10:
            return float(i)
    return -99.0


def onsetMozambique(x):
    """at least 20 mm of accumulated rainfall in 3 days, not followed by a period
    of 10 consecutive days with rainfall < 1 mm in the following 21 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 3), 20):
        if i + 22 <= len(x) and longestDrySpell(x[i + 1:i + 22]) < 10:
            return float(i)
    return -99.0


def onsetNamibia(x):
    """first day with rainfall >= 0.1 mm on which the 10 days starting that day
    accumulate at least 10 mm, with at least 2 of those days having >= 0.1 mm
    (returns the first day of the 10-day window, not the last)"""
    if np.isnan(x).any():
        return np.nan
    for i in np.where(x >= 0.1)[0]:
        w = x[i:i + 10]
        if i + 10 <= len(x) and w.sum() >= 10 and np.sum(w >= 0.1) >= 2:
            return float(i)
    return -99.0
 

def onsetSouthAfrica(x):
    """at least 25 mm of accumulated rainfall in 5 days, not followed by a period
    of 10 consecutive days with rainfall < 1 mm in the following 21 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 5), 25):
        if i + 22 <= len(x) and longestDrySpell(x[i + 1:i + 22]) < 10:
            return float(i)
    return -99.0

def onsetTanzania(x):
    """more than 20 mm of accumulated rainfall in 4 days, with at least 2 days
    of rainfall >= 1 mm, not followed by a period of 10 consecutive days with
    rainfall < 1 mm in the following 30 days"""
    if np.isnan(x).any():
        return np.nan
    s, wet = trailingSum(x, 4), trailingCount(x, 4, 1.0)
    for i in _hits(s, 20, strict=True):
        if wet[i] >= 2 and i + 31 <= len(x) and longestDrySpell(x[i + 1:i + 31]) < 10:
            return float(i)
    return -99.0


def onsetZambia(x):
    """at least 20 mm of accumulated rainfall in 5 days, with at least 3 days
    of rainfall >= 0.85 mm, not followed by a period of more than 10 consecutive
    days with rainfall < 0.85 mm in the following 21 days"""
    if np.isnan(x).any():
        return np.nan
    s, wet = trailingSum(x, 5), trailingCount(x, 5, 0.85)
    for i in _hits(s, 20):
        if wet[i] >= 3 and i + 22 <= len(x) and longestDrySpell(x[i + 1:i + 22], 0.85) <= 10:
            return float(i)
    return -99.0




def onsetZimbabwe(x):
    """at least 20 mm of accumulated rainfall in 2 days, not followed by a period
    of 10 consecutive days with rainfall < 1 mm in the following 30 days"""
    if np.isnan(x).any():
        return np.nan
    for i in _hits(trailingSum(x, 2), 20):   # a single 20 mm day also qualifies
        if i + 31 <= len(x) and longestDrySpell(x[i + 1:i + 31]) < 10:
            return float(i)
    return -99.0
