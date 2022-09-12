#
# This file is part of LiteX.
#
# Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect.axi import  AXIStreamInterface

class TestAXIStream(unittest.TestCase):
    def test_axi_stream_syntax(self):
        axis = AXIStreamInterface(data_width=32)
        axis = AXIStreamInterface(data_width=32, keep_width=4)
        axis = AXIStreamInterface(data_width=32, keep_width=4, id_width=4)
        axis = AXIStreamInterface(data_width=32, keep_width=4, id_width=4, dest_width=4)
        axis = AXIStreamInterface(data_width=32, keep_width=4, id_width=4, dest_width=4, user_width=4)

    def test_axi_stream_get_ios(self):
        axis = AXIStreamInterface(data_width=32, keep_width=4, id_width=4, dest_width=4, user_width=4)
        pads = axis.get_ios()
