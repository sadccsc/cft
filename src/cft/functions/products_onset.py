"""
Onset kernels 0 - all in plain numpy as datetime decorator is not passed

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
