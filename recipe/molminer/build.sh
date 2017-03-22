#!/bin/bash

python setup.py install --single-version-externally-managed --record record.txt

if [ -n "$MOLMINER_DATA_PATH" ]
then
    cp -r $MOLMINER_DATA_PATH/{bin,etc,lib} $PREFIX
    mkdir -p $PREFIX/share/molminer
    cp -r $MOLMINER_DATA_PATH/share/molminer/{graphicsmagick,openbabel,tessdata} $PREFIX/share/molminer
else
    echo "MOLMINER_DATA_PATH environmental variable is not set!"
    exit 1
fi