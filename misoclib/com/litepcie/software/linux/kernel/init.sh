#!/bin/sh
# TODO: use udev instead

insmod litepcie.ko

major=$(awk '/ litepcie$/{print $1}' /proc/devices)
mknod -m 666 /dev/litepcie0 c $major 0
