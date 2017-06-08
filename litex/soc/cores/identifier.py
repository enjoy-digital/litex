from litex.gen import *


class Identifier(Module):
    def __init__(self, ident):
        contents = list(ident.encode())
        l = len(contents)
        if l > 256:
            raise ValueError("Identifier string must be 255 characters or less")
        self.mem = Memory(8, len(contents), init=contents)

    def get_memories(self):
        return [(True, self.mem)]
