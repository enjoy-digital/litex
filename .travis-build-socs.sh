#!/usr/bin/env bash

set -e

# Some colors, use it like following;
# echo -e "Hello ${YELLOW}yellow${NC}"
GRAY='\033[0;30m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

SPACER="echo -e ${GRAY} - ${NC}"

travis_fold start "environment.create"
travis_time_start
echo -e "Setting up basic ${YELLOW}conda environment${NC}"
echo "-------------------------------------------------------------------"
conda env create -f environment.yml
source activate litex
echo "-------------------------------------------------------------------"
travis_time_finish
travis_fold end "environment.create"

$SPACER

SOC_FILES=$(find litex/boards/targets -name \*.py | grep -v sim | grep -v "__")

COUNT=4

for SOC_FILE in $SOC_FILES; do
	SOC=$(echo $SOC_FILE | sed -e's/\.py$//' -e's-/-.-g')
	TARGET=$(echo $SOC | sed -e's/.*\.//')

	travis_fold start "$SOC.1"
	travis_time_start
	echo -e "Building ${GREEN}${TARGET}${NC} (${PURPLE}${SOC}${NC})"
	echo "-------------------------------------------------------------------"
	python -m $SOC --no-compile-gateware
	echo "-------------------------------------------------------------------"
	travis_time_finish
	travis_fold end "$SOC.1"
	travis_fold start "$SOC.2"
	echo -e "Output of building ${GREEN}${TARGET}${NC} (${PURPLE}${SOC}${NC})"
	echo "-------------------------------------------------------------------"
	find soc_*$TARGET* | sort
	echo "-------------------------------------------------------------------"
	travis_fold end "$SOC.2"

	$SPACER
done
