#!/bin/bash
#
# This script downloads and compiles source code of dependencies to install the CFT
#
echo
echo "installing CFT..."
echo
SCRIPT=$(readlink -f $0)
cwd=`dirname $SCRIPT`
echo "CFT directory: $cwd"
echo
export PYTHONPATH=$cwd/python3
export PATH=${PYTHONPATH}/bin:$PATH 
export LD_LIBRARY_PATH=${PYTHONPATH}/lib:${PYTHONPATH}/lib64:$LD_LIBRARY_PATH 
export LDFLAGS="-L${PYTHONPATH}/lib -L${PYTHONPATH}/lib64" 
export LD_RUN_PATH=${PYTHONPATH}/lib:${PYTHONPATH}/lib64
export CPPFLAGS="-I${PYTHONPATH}/include" 

cd $cwd
mkdir -p source 
if [ -d source ]; then
  cd $cwd/source
  wget --no-check-certificate http://www.cpan.org/src/5.0/perl-5.20.1.tar.gz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download perl. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "perl-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing ${lib##*/}..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "perl-*" -type d)
    ./Configure -des -Dprefix=${PYTHONPATH}
    make
    make install
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://www.openssl.org/source/openssl-3.0.0-alpha13.tar.gz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download openssl. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "openssl-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing ${lib##*/}..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "openssl-*" -type d)
    ./config --prefix=${PYTHONPATH} --openssldir=${PYTHONPATH}
    make -j4
    make install -j4
    if [[ $? -ne 0 ]]; then
       echo "error, openssl could not be installed"
       exit
    fi
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://github.com/Kitware/CMake/releases/download/v3.23.0/cmake-3.23.0.tar.gz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download cmake. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "cmake-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing ${lib##*/}..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "cmake-*" -type d)
    ./bootstrap --prefix=${PYTHONPATH}
    make
    make install
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate http://download.osgeo.org/geos/geos-3.10.2.tar.bz2 -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download geos. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "geos-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing ${lib##*/}..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "geos-*" -type d)
    mkdir _build
    cd _build
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=${PYTHONPATH} ..
    make
    make install
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://download.open-mpi.org/release/open-mpi/v4.0/openmpi-4.0.4.tar.bz2 -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download openmpi. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "openmpi-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing ${lib##*/}..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "openmpi-*" -type d)
    ./configure --prefix=${PYTHONPATH}
    make install -j4
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://gcc.gnu.org/pub/libffi/libffi-3.3.tar.gz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download libffi. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "libffi-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing libffi..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "libffi-*" -type d)
    ./configure --prefix=${PYTHONPATH}
    make install -j4
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://deac-fra.dl.sourceforge.net/project/lzmautils/xz-5.2.5.tar.xz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download xz. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "xz-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing xz..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "xz-*" -type d)
    ./configure --prefix=${PYTHONPATH}
    make install -j4
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://zlib.net/zlib-1.2.12.tar.gz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download zlib. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "zlib-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing zlib..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "zlib-*" -type d)
    ./configure --prefix=${PYTHONPATH}
    make install -j4
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://sourceware.org/pub/bzip2/bzip2-1.0.8.tar.gz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download bzip2. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "bzip2-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing bzip2..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "bzip2-*" -type d)
    make
    make clean
    make -f Makefile-libbz2_so
    makelink=$(grep "ln -s " Makefile-libbz2_so | xargs)
    libbz2_so=$(echo $makelink | awk '{print $3}')
    make install PREFIX=${PYTHONPATH}
    cp -v $libbz2_so ${PYTHONPATH}/lib
    cd ${PYTHONPATH}/lib
    $makelink
  fi
  echo
  cd $cwd/source
  wget --no-check-certificate https://www.python.org/ftp/python/3.8.5/Python-3.8.5.tar.xz -c
  if [[ $? -ne 0 ]]; then
     echo "error, could not download Python. check URL in the script and update if necessary"
     exit
  fi
  lib=$(find ./ -maxdepth 1 -name "Python-*" -type f | tail -1)
  if [ -n $lib ]; then
    echo
    echo "installing python..."
    tar xf $lib
    cd $(find ./ -maxdepth 1 -name "Python-*" -type d)
    ./configure --prefix=${PYTHONPATH} --with-openssl=${PYTHONPATH} --enable-optimizations
    make -j4
    make install
  fi
fi

echo "installing python libraries..."
cd $cwd
echo "upgrading pip"
pip3 install --upgrade pip
echo
echo "installing other dependencies..."
if [ ! -f $cwd/requirements.txt ]; then
   echo "could not locate requirements file. exit"
   exit 1
fi 
pip3 install --upgrade -r $cwd/requirements.txt
if [ $? -ne 0 ]; then
  exit
fi
if [ -n $(which mpirun) ]; then
  pip3 install --upgrade  mpi4py
  [ $? -ne 0 ] && echo "MPI support installed"
fi
echo
echo "creating environmental variables file"
echo "export PATH=${PYTHONPATH}/bin:$PATH" > ${PYTHONPATH}/bin/activate
echo "export LD_LIBRARY_PATH=${PYTHONPATH}/lib:$LD_LIBRARY_PATH" >> ${PYTHONPATH}/bin/activate
echo "export LD_RUN_PATH=${PYTHONPATH}/lib" >> ${PYTHONPATH}/bin/activate
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

