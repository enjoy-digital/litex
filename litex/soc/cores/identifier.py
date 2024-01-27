#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

# Identifier ---------------------------------------------------------------------------------------

class Identifier(LiteXModule):
    def __init__(self, ident):
        contents = list(ident.encode())
        l = len(contents)
        if l > 255:
            raise ValueError("Identifier string must be 255 characters or less")
        contents.append(0)
        self.mem = Memory(8, len(contents), init=contents)

    def get_memories(self):
        return [(True, self.mem)]
