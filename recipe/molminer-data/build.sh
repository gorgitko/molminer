#!/bin/bash

if [ -n "$MOLMINER_DATA_PATH" ]
then
    mkdir -p $PREFIX/share/molminer
    cp -r $MOLMINER_DATA_PATH/share/molminer/{chemspot,osra} $PREFIX/share/molminer
else
    echo "MOLMINER_DATA_PATH environmental variable is not set!"
    exit 1
fi