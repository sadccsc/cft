#!/bin/bash
echo
echo "installing CFT..."
echo
SCRIPT=$(readlink -f $0)
cwd=`dirname $SCRIPT`
echo "CFT directory: $cwd"
echo
echo "creating virtual python environment..."
cd $cwd
python3 -m venv python3 &>/dev/null
if [ $? -ne 0 ]; then
  echo "there was an error creating the virtual environment"
  echo "ensure you have python3 and required dependencies installed:  sudo apt install python3-pip python3-venv libffi-dev"
  exit
fi
source python3/bin/activate

echo
echo "installing other dependencies..."
if [ ! -f $cwd/requirements.txt ]; then
   echo "could not locate requirements file. exit"
   exit 1
fi 
echo
pip3 install --upgrade pip
echo
pip3 install --upgrade -r $cwd/requirements.txt
if [ $? -ne 0 ]; then
  exit
fi
if [ -n $(which mpirun) ]; then
  pip3 install --upgrade  mpi4py
  [ $? -ne 0 ] && echo "MPI support installed"
fi

echo
echo "creating desktop shortcut"
echo "#!/usr/bin/env xdg-open" > $cwd/CFT.desktop
echo "[Desktop Entry]" >> $cwd/CFT.desktop
echo "Version=1.0" >> $cwd/CFT.desktop
echo "Type=Application" >> $cwd/CFT.desktop
echo "Terminal=false" >> $cwd/CFT.desktop
echo "Exec=${cwd}/start_linux.sh" >> $cwd/CFT.desktop
echo "Name=CFT" >> $cwd/CFT.desktop
echo "Comment=CFT" >> $cwd/CFT.desktop
echo "Icon=${cwd}/icon/cft.ico" >> $cwd/CFT.desktop
chmod 777 $cwd/CFT.desktop
chmod +x ${cwd}/start_linux.sh
[ -d ~/Desktop ]  && cp $cwd/CFT.desktop ~/Desktop/
echo "installation completed."
deactivate
