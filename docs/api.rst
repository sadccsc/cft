API Reference
=============

This page documents only the main entry points of each module - the
functions intended to be called directly from Python, without a GUI.
Internal helper functions are not listed here.

Forecast
--------

.. currentmodule:: cft.functions.functions_forecast

.. autofunction:: computeModelNoGui

Download
--------

.. currentmodule:: cft.functions.functions_download

.. autofunction:: downloadPredictand

.. autofunction:: downloadGriddedPredictor

.. autofunction:: downloadFcstPredictor

.. autofunction:: downloadIndexPredictor

Verification
------------

.. currentmodule:: cft.functions.functions_verification

.. autofunction:: execVerification

Zoning
------

.. currentmodule:: cft.functions.functions_zoning

.. autofunction:: season_average

.. autofunction:: season_cumulation
