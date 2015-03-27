#!/bin/sh
# Copyright Robert Jordens <robert@joerdens.org> 2014,2015

# assuming your xilinx toolchain lives in /opt/Xilinx,
# run `strace-tailor.sh [synthesis script] [options]`
# then in your current directory, `opt/Xilinx/*` is the
# minimal toolchain required for this synthesis script run.

PREFIX=\\/opt\\/Xilinx\\/

strace -e trace=file,process -f -o strace.log $@
sed -n "s/^.*\"\\(${PREFIX}[^\"]*\\)\".*$/\\1/p" strace.log \
	| sort | uniq | tr '\n' '\0' \
	| xargs -0 cp --parent --no-dereference --preserve=all -t .
