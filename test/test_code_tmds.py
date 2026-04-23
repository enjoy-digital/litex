#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.cores.code_tmds import TMDSEncoder, control_tokens


# Reference Model ----------------------------------------------------------------------------------

def tmds_encode(d, c, de, cnt):
    """Pure-Python reference TMDS encoder (DVI 1.0).

    Returns (out10, new_cnt).
    """
    if not de:
        return control_tokens[c & 0x3], 0

    d   = d & 0xff
    n1d = bin(d).count("1")

    # Stage 1: q_m = XOR or XNOR chain, q_m[8] signals which.
    q_m = [d & 1] + [0]*8
    if n1d > 4 or (n1d == 4 and (d & 1) == 0):
        for i in range(1, 8):
            q_m[i] = q_m[i-1] ^ ((d >> i) & 1) ^ 1
        q_m[8] = 0
    else:
        for i in range(1, 8):
            q_m[i] = q_m[i-1] ^ ((d >> i) & 1)
        q_m[8] = 1

    n1 = sum(q_m[:8])
    n0 = 8 - n1

    # Stage 2: DC-balance.
    if cnt == 0 or n1 == n0:
        out9 = 1 ^ q_m[8]
        out8 = q_m[8]
        if q_m[8]:
            out07   = q_m[:8]
            new_cnt = cnt + n1 - n0
        else:
            out07   = [1 ^ b for b in q_m[:8]]
            new_cnt = cnt + n0 - n1
    elif (cnt > 0 and n1 > n0) or (cnt < 0 and n0 > n1):
        out9    = 1
        out8    = q_m[8]
        out07   = [1 ^ b for b in q_m[:8]]
        new_cnt = cnt + 2*q_m[8] + n0 - n1
    else:
        out9    = 0
        out8    = q_m[8]
        out07   = q_m[:8]
        new_cnt = cnt - 2*(1 - q_m[8]) + n1 - n0

    out = (out9 << 9) | (out8 << 8)
    for i, b in enumerate(out07):
        out |= (b & 1) << i
    return out, new_cnt


# Helpers ------------------------------------------------------------------------------------------

# The hardware TMDSEncoder has a 4-stage pipeline (d → q_m → q_m_r → out, and a matching 3-stage
# pipeline on c/de before the final stage).
TMDS_LATENCY = 4


def run_encoder(items, flush=TMDS_LATENCY + 4):
    """Drive `items` = list of (d, c, de) through a TMDSEncoder and return sampled `out` per cycle."""
    dut     = TMDSEncoder()
    outputs = []

    def pump():
        for d, c, de in items:
            yield dut.d.eq(d)
            yield dut.c.eq(c)
            yield dut.de.eq(de)
            yield
            outputs.append((yield dut.out))
        yield dut.de.eq(0)
        for _ in range(flush):
            yield
            outputs.append((yield dut.out))
    run_simulation(dut, pump())
    return outputs


# Tests --------------------------------------------------------------------------------------------

class TestCodeTMDS(unittest.TestCase):
    def test_control_tokens(self):
        # Drive each of the 4 control codes with de=0 for a few cycles and check the matching
        # token appears on the output after the pipeline latency.
        items = []
        for c in range(4):
            items += [(0, c, 0)]*6
        outputs = run_encoder(items)

        for i in range(TMDS_LATENCY, len(items)):
            _, c, _ = items[i - TMDS_LATENCY]
            self.assertEqual(outputs[i], control_tokens[c],
                f"i={i} c={c}: got 0b{outputs[i]:010b}, want 0b{control_tokens[c]:010b}")

    def test_against_reference(self):
        # Fuzz 1000 random bytes against the reference model.
        prng  = random.Random(42)
        items = [(prng.randrange(256), 0, 1) for _ in range(1000)]

        # Prime pipeline with a few control cycles so the initial cnt is zero and well defined.
        priming = [(0, 0, 0)]*TMDS_LATENCY
        outputs = run_encoder(priming + items)

        cnt      = 0
        expected = []
        for d, c, de in priming + items:
            e, cnt = tmds_encode(d, c, de, cnt)
            expected.append(e)

        for i in range(TMDS_LATENCY, len(priming + items)):
            src = priming + items
            self.assertEqual(outputs[i], expected[i - TMDS_LATENCY],
                f"i={i} d=0x{src[i - TMDS_LATENCY][0]:02x}: "
                f"got 0b{outputs[i]:010b}, want 0b{expected[i - TMDS_LATENCY]:010b}")

    def test_de_transition(self):
        # Exiting the control region should reset cnt to 0, so a sequence starting from a
        # control→data transition must match the reference model starting at cnt=0.
        prng  = random.Random(7)
        datas = [(prng.randrange(256), 0, 1) for _ in range(64)]
        items = [(0, 0, 0)]*8 + datas
        outputs = run_encoder(items)

        cnt      = 0
        expected = []
        for d, c, de in items:
            e, cnt = tmds_encode(d, c, de, cnt)
            expected.append(e)

        for i in range(TMDS_LATENCY, len(items)):
            self.assertEqual(outputs[i], expected[i - TMDS_LATENCY])


if __name__ == "__main__":
    unittest.main()
