[> Bare Metal Demo App
----------------------

This directory provides a minimal bare metal demo app that demonstrates how to easily create a bare metal C application and load it/run it on the CPU of a SoC.

[> Build
--------

Imagine you just built the Arty example design from LiteX-Boards. Build the demo app as follows; where the build path is the path to your previously built Arty build directory:
```
litex_bare_metal_demo --build-path=build/arty/
```

[> Load
-------

Loading the compiled demo app can be done in different ways as explain in LiteX's wiki:
https://github.com/enjoy-digital/litex/wiki/Load-Application-Code-To-CPU

Since our app is small and for simplicity we'll just load it over serial here:
 `$ lxterm /dev/ttyUSBX --kernel=demo.bin`

You should see the minimal demo app running and should be able to interact with it:

    --============== Boot ==================--
    Booting from serial...
    Press Q or ESC to abort boot completely.
    sL5DdSMmkekro
    [LXTERM] Received firmware download request from the device.
    [LXTERM] Uploading demo.bin to 0x40000000 (9264 bytes)...
    [LXTERM] Upload complete (9.8KB/s).
    [LXTERM] Booting the device.
    [LXTERM] Done.
    Executing booted program at 0x40000000

    --============= Liftoff! ===============--

    LiteX minimal demo app built Dec 10 2020 17:13:02

    Available commands:
    help               - Show this command
    reboot             - Reboot CPU
    led                - Led demo
    donut              - Spinning Donut demo
    litex-demo-app> led
    Led demo...
    Counter mode...
    Shift mode...
    Dance mode...
    litex-demo-app> donut
    Donut demo...

                                          $$$$$@@@@@
                                      $##########$$$$$$$$
                                   ###*!!!!!!!!!***##$$$$$$
                                 ***!!====;;;;===!!**###$$$$#
                                **!===;;;:::::;:===!!**####$##
                              !*!!==;;:~-,,.,-~::;;=!!**#######!
                              !!!!=;:~-,.......-~::==!!***#####*
                             !!!!==;~~-.........,-:;==!!***###**!
                             !**!!=;:~-...     ..-:;=!!!********!
                            ;!*#####*!!;.       ~:;==!!!******!!=
                            :!*###$$$$#*!      :;==!!!!!****!!!=;
                            ~=!*#$$$@@@$$##!!!!!!!!!!!!****!!!!=;
                             ;=!*#$$$@@@@$$#*******!*!!*!!!!!==;~
                             -;!*###$$$$$$$###******!!!!!!!===;~
                              -;!!*####$#####******!!!!!!==;;:-
                               ,:=!!!!**#**#***!!!!!!!====;:~,
                                 -:==!!!*!!*!!!!!!!===;;;:~-
                                   .~:;;========;=;;:::~-,
                                      .--~~::::~:~~--,.
    litex-demo-app>

[> Going further
----------------
To create more complex apps, feel free to explore the source code of the BIOS or other open source projects build with LiteX at https://github.com/enjoy-digital/litex/wiki/Projects.
