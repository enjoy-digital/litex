#!/bin/bash

set -x
set -e

source activate litex

SOC_FILES=$(find litex/boards/targets -name \*.py | grep -v sim | grep -v "__")

for SOC_FILE in $SOC_FILES; do
	SOC=$(echo $SOC_FILE | sed -e's/\.py$//' -e's-/-.-g')
	python -m $SOC --no-compile-gateware
done

find soc_* | sort
