from migen.fhdl.std import Module, bits_for
from migen.bank.description import CSR


class GenericBank(Module):
    def __init__(self, description, busword):
        # Turn description into simple CSRs and claim ownership of compound CSR modules
        self.simple_csrs = []
        for c in description:
            if isinstance(c, CSR):
                self.simple_csrs.append(c)
            else:
                c.finalize(busword)
                self.simple_csrs += c.get_simple_csrs()
                self.submodules += c
        self.decode_bits = bits_for(len(self.simple_csrs)-1)


def get_offset(description, name, busword):
    offset = 0
    for c in description:
        if c.name == name:
            return offset
        offset += (c.size + busword - 1)//busword
    raise KeyError("CSR not found: "+name)
