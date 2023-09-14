#!/bin/bash
SCRIPT=$(readlink -f $0)
cwd=`dirname $SCRIPT`
PYTHONPATH=$cwd/python3
cd $cwd
if [ -f ${PYTHONPATH}/bin/activate ]; then
  source ${PYTHONPATH}/bin/activate
else
  export PATH=${PYTHONPATH}/bin:$PATH 
  export LD_LIBRARY_PATH=${PYTHONPATH}/lib:${PYTHONPATH}/lib64:$LD_LIBRARY_PATH 
fi
if [ $? -ne 0 ]; then
  zenity --error --text="Cannot load required python environment, ensure installation script has been executed"
  exit
fi

if [ ! -f $1 ]; then
   zenity --error --text="Cannot locate $1, ensure installation script has been executed"
   exit
fi
python3 $1 
