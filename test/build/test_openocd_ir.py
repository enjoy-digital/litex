#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from litex.build.openocd import OpenOCD

# Intel/Altera: JTAGPHY gates the stream on AlteraJTAG's sel (the hard JTAG block's usr1user), so
# the stream must use the USER1 instruction (0x00E).
@pytest.mark.parametrize("chip,ir", [("10m50", 0xe), ("ep4ce", 0xe), ("5cgtfd9", 0xe)])
def test_intel_stream_ir_is_user1(tmp_path, chip, ir):
    cfg = tmp_path / "board.cfg"
    cfg.write_text(f"set _CHIPNAME {chip}\njtag newtap $_CHIPNAME tap -irlen 10\n")
    assert OpenOCD(str(cfg)).get_ir(1, str(cfg)) == ir
