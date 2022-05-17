[> Bare Metal Demo App
----------------------

This directory provides a minimal bare metal demo app that demonstrates how to easily create a bare metal C application and load it/run it on the CPU of a SoC.

[> Build and Load over LiteX-Term
---------------------------------

To build a LiteX SoC for the Arty board (available in LiteX-Boards) and build the demo app for it, execute the following commands:
```
python3 -m litex_boards.targets.digilent_arty --build --load
litex_bare_metal_demo --build-path=build/digilent_arty
```
Where `--build-path` is the build path to the Arty build directory. The Arty board is used here but almost any another board supported in LiteX-Boards could be used. When no external RAM is provided directly by the board, `--integrated-main-ram-size` argument could be used to add some integrated RAM in the SoC and be able to execute the demo from it. (ex `--integrated-main-ram-size=0x8000` will add 32KB of integrated RAM).

Loading the compiled demo app can be done in different ways as explain in LiteX's wiki:
https://github.com/enjoy-digital/litex/wiki/Load-Application-Code-To-CPU

Since our app is small and for simplicity we'll just load it over serial here:
 `$ litex_term /dev/ttyUSBX --kernel=demo.bin`

You should see the minimal demo app running and should be able to interact with it:

    --============== Boot ==================--
    Booting from serial...
    Press Q or ESC to abort boot completely.
    sL5DdSMmkekro
    [LITEX-TERM] Received firmware download request from the device.
    [LITEX-TERM] Uploading demo.bin to 0x40000000 (9264 bytes)...
    [LITEX-TERM] Upload complete (9.8KB/s).
    [LITEX-TERM] Booting the device.
    [LITEX-TERM] Done.
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

[> Replace the LiteX BIOS with the Demo App
-------------------------------------------
In some cases, we'll just want to replace the LiteX BIOS with our custom app. This demo can be used as a basis to create a such custom app.

The demo will be recompiled to target the ROM of the SoC:
```
litex_bare_metal_demo --build-path=build/arty/ --mem=rom
```

The SoC can then be re-compiled to integrate the demo app in the ROM with:
```
python3 -m litex_boards.targets.digilent_arty --integrated-rom-init=demo.bin --build --load
```

When loading the bitstream, you should then directly see the demo app executed:
```
    LiteX minimal demo app built Dec 10 2020 17:13:02

    Available commands:
    help               - Show this command
    reboot             - Reboot CPU
    led                - Led demo
    donut              - Spinning Donut demo
    litex-demo-app>
```


[> Going further
----------------
To create more complex apps, feel free to explore the source code of the BIOS or other open source projects build with LiteX at https://github.com/enjoy-digital/litex/wiki/Projects.
