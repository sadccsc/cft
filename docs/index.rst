CFT — Climate Forecasting Toolbox
==================================

A Python-based tool for statistical climate forecasting, developed by the
SADC Climate Services Centre (CSC).

.. toctree::
   :maxdepth: 2
   :caption: Contents

   api

Installation
------------

.. code-block:: bash

   mamba create --name cft-env python=3.12
   mamba activate cft-env
   mamba install -c conda-forge gdal=3.13.2
   pip install sadc-cft

See the `project README <https://github.com/sadc-csc/cft>`_ for full
installation and GUI usage instructions.

Using CFT without the GUI
--------------------------

Each module's main computation can be called directly from Python - see
:doc:`api` for the full reference. For example:

.. code-block:: python

   from cft.functions.functions_forecast import computeModelNoGui

   computeModelNoGui(config)

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
