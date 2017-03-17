#!/bin/bash
# first argument is maximum amount of memory (in GB) which can be used by ChemSpot process

args=( "$@" )

if [[ $1 == "" ]]
then
    echo "argument 1 not found: amount of memory [GB] for Java heap" >&2
    exit 1
fi

digit_regex="^[0-9]+$"

if ! [[ $1 =~ $digit_regex ]]
then
   echo "argument 1: not a number." >&2
   exit 1
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

java -Xmx${args[0]}G -jar $DIR/chemspot.jar ${args[@]:1}