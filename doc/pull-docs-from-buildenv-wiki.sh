#!/bin/bash

# Soft-CPU - Description about supported Soft-CPUs.
# BIOS     - Information about the BIOS and what it is used for.
# Firmware - Information about compatible Firmware.

for page in Soft-CPU BIOS Firmware; do
	curl https://raw.githubusercontent.com/wiki/timvideos/litex-buildenv/${page}.md > ${page}.md
	git add ${page}.md
done

GIT_MSG=$(tempfile) || exit
trap "rm -f -- '$GIT_MSG'" EXIT
git commit --message "Updating documents from LiteX BuildEnv Wiki"
