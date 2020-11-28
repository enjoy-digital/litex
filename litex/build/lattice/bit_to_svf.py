#!/usr/bin/env python3

# Very basic bitstream to SVF converter
# This file is Copyright (c) 2018 David Shah <dave@ds0.me>

import sys
import textwrap

max_row_size = 100000

def bitreverse(x):
    y = 0
    for i in range(8):
        if (x >> (7 - i)) & 1 == 1:
            y |= (1 << i)
    return y

def bit_to_svf(bit, svf):
    with open(bit, 'rb') as bitf:
        bs = bitf.read()
        # Autodetect IDCODE from bitstream
        idcode_cmd = bytes([0xE2, 0x00, 0x00, 0x00])
        idcode = None
        for i in range(len(bs) - 4):
            if bs[i:i+4] == idcode_cmd:
                idcode = bs[i+4] << 24
                idcode |= bs[i+5] << 16
                idcode |= bs[i+6] << 8
                idcode |= bs[i+7]
                break
        if idcode is None:
            print("Failed to find IDCODE in bitstream, check bitstream is valid")
            sys.exit(1)
        print("IDCODE in bitstream is 0x%08x" % idcode)
        bitf.seek(0)
        with open(svf, 'w') as svf:
            print("""
    HDR	0;
    HIR	0;
    TDR	0;
    TIR	0;
    ENDDR	DRPAUSE;
    ENDIR	IRPAUSE;
    STATE	IDLE;
            """, file=svf)
            print("""
    SIR	8	TDI  (E0);
    SDR	32	TDI  (00000000)
            TDO  ({:08X})
            MASK (FFFFFFFF);
            """.format(idcode), file=svf)
            print("""
    SIR	8	TDI  (1C);
    SDR	510	TDI  (3FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                 FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF);

    SIR	8	TDI  (C6);
    SDR	8	TDI  (00);
    RUNTEST	IDLE	2 TCK	1.00E-02 SEC;

    SIR	8	TDI  (3C);
    SDR	32	TDI  (00000000)
            TDO  (00000000)
            MASK (0000B000);

    SIR	8	TDI  (46);
    SDR	8	TDI  (01);
    RUNTEST	IDLE	2 TCK	1.00E-02 SEC;

    SIR	8	TDI  (7A);
    RUNTEST	IDLE	2 TCK	1.00E-02 SEC;

            """, file=svf)
            while True:
                chunk = bitf.read(max_row_size//8)
                if not chunk:
                    break
                # Convert chunk to bit-reversed hex
                br_chunk = [bitreverse(x) for x in chunk]
                hex_chunk = ["{:02X}".format(x) for x in reversed(br_chunk)]
                print("\n".join(textwrap.wrap("SDR {} TDI ({});".format(8*len(chunk), "".join(hex_chunk)), 100)), file=svf)

            print("""
    SIR	8	TDI  (FF);
    RUNTEST	IDLE	100 TCK	1.00E-02 SEC;


    SIR	8	TDI  (C0);
    RUNTEST	IDLE	2 TCK	1.00E-03 SEC;
    SDR	32	TDI  (00000000)
            TDO  (00000000)
            MASK (FFFFFFFF);

    ! Shift in ISC DISABLE(0x26) instruction
    SIR	8	TDI  (26);
    RUNTEST	IDLE	2 TCK	2.00E-01 SEC;
    ! Shift in BYPASS(0xFF) instruction
    SIR	8	TDI  (FF);
    RUNTEST	IDLE	2 TCK	1.00E-03 SEC;

    ! Shift in LSC_READ_STATUS(0x3C) instruction
    SIR	8	TDI  (3C);
    SDR	32	TDI  (00000000)
            TDO  (00000100)
            MASK (00002100);
            """, file=svf)

if __name__ == "__main__":
    bit_to_svf(sys.argv[1], sys.argv[2])