#! /bin/bash
env=cft-v5.0

# Check if mamba is installed
if ! command -v mamba &> /dev/null; then
    echo "Mamba not found. Installing..."
    conda install -y mamba -n base -c conda-forge
else
    echo "Mamba is already installed."
fi

echo creating conda enviroment
mamba env create -f environment.yml
echo done

