#!/bin/sh
# Copyright Robert Jordens <robert@joerdens.org> 2014,2015

# assuming your xilinx toolchain lives in /opt/Xilinx,
# run `strace_tailor.sh /opt/Xilinx/ [synthesis script] [options]`,
# e.g. for the pipistrello target of misoc:
#   strace_tailor.sh /opt/Xilinx/ ./make.py -t pipistrello build-bitstream
# then in your current directory, `opt/Xilinx/*` is the
# minimal toolchain required for this synthesis script run.

PREFIX=$1
shift
strace -e trace=file,process -f -o strace.log $@
sed -n 's|^.*"\('"$PREFIX"'[^"]*\)".*$|\1|p' strace.log \
	| sort | uniq | xargs -d '\n' \
	cp --parent --no-dereference --preserve=all -t .
