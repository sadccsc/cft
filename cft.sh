#! /bin/bash

# Detect conda location
if [ -z "$CONDA_EXE" ]; then
    # fallback: try 'which conda'
    CONDA_EXE=$(which conda)
fi

if [ -z "$CONDA_EXE" ]; then
    echo "Conda not found in PATH"
    exit 1
fi

# Get base conda directory
CONDA_BASE=$(dirname $(dirname "$CONDA_EXE"))

# Source conda.sh from base
source "$CONDA_BASE/etc/profile.d/conda.sh"

conda activate cft-v5.1
python cft.py

