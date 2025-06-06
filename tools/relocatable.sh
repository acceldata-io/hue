#!/bin/bash
# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

usage() {
  echo "
  Make a Hue installation relocatable. Run this in the installation
  directory created by 'make install', before you relocate it.
  Usage:
    ./tools/relocatable.sh [python_version]
  Example:
    ./tools/relocatable.sh python3.9
  "
  exit 1
}

# Check for arguments
PYTHON_VER=""
if [ $# -gt 1 ]; then
  usage
elif [ $# -eq 1 ]; then
  PYTHON_VER=$1
  echo "Using Python version: $PYTHON_VER"
fi

find_os() {
  unameOut="$(uname -s)"
  case "${unameOut}" in
    Linux*)     machine=Linux;;
    Darwin*)    machine=Mac;;
    CYGWIN*)    machine=Cygwin;;
    MINGW*)     machine=MinGw;;
    *)          machine="UNKNOWN:${unameOut}"
  esac
  echo ${machine}
}

find_home() {
  runningos=$(find_os)
  WORK_DIR=""
  if [[ ${runningos} == "Linux" ]]; then
    WORK_DIR=$(dirname "$(readlink -f "$0" || echo "$argv0")")
  elif [[ ${runningos} == "Mac" ]]; then
    WORK_DIR="$( cd "$( dirname "$argv0" )" && pwd )"
  else
    echo "Not Supported " $runningos
    exit 1
  fi
  echo ${WORK_DIR}
}

# We're in <hue_root>/tools
CURR_DIR=$(find_home)

if [[ $CURR_DIR == */hue ]]; then
  HUE_ROOT=$CURR_DIR
elif [[ $CURR_DIR == */tools ]]; then
  HUE_ROOT=$(dirname $CURR_DIR)
fi

BLD_DIR_BIN="$BLD_DIR_ENV/bin"
ENV_PYTHON="$BLD_DIR_BIN/python"

VIRTUAL_BOOTSTRAP="$CURR_DIR/virtual-bootstrap/virtual-bootstrap.py"

if [[ ! -e $ENV_PYTHON ]]; then
  echo "Is $ENV_PYTHON available?"
  echo "Failing to perform relocataion"
  exit 127
fi

if [[ ! -e $VIRTUAL_BOOTSTRAP ]]; then
  echo "Is $VIRTUAL_BOOTSTRAP available?"
  echo "Failing to perform relocataion"
  exit 127
fi

export PATH=$(dirname $ENV_PYTHON):$PATH

PYVER=$($ENV_PYTHON -V 2>&1 | awk '{print $2}' | cut -d '.' -f 1,2)
BIN_DIR=$(dirname $SYS_PYTHON)
# Step 1. Fix virtualenv
if [[ "$PYVER" == "3."[8-9]* || "$PYVER" == "3.11" ]]; then
  echo "Python version is 3.8 or greater"
  pushd .
  cd $HUE_ROOT
  $SYS_PYTHON $BIN_DIR/virtualenv-make-relocatable "$BLD_DIR_ENV"
  # $SYS_PYTHON $VIRTUAL_BOOTSTRAP --relocatable_pth "$BLD_ENV_REL"
  popd
fi

# Step 1b. Fix any broken lib64 directory
LIB64="$HUE_ROOT/$BLD_ENV_REL/lib64"
if [ -L "$LIB64" -a ! -e "$LIB64" ] ; then
  rm "$LIB64"
  ln -s lib "$LIB64"
fi

# Step 2. Fix .ini symlinks for all apps (make them relative)
for app in $HUE_ROOT/apps/* ; do
  if [ -d "$app/conf" ] ; then
    appname=$(basename $app)
    pushd "$HUE_ROOT/desktop/conf"
    ln -sfv ../../apps/$appname/conf/*.ini .
    popd
  fi
done

# Step 3. Clean up any old .pyc files
find "$HUE_ROOT" . -name "*.pyc" -exec rm -f {} \;
