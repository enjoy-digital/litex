class LiteScopeIODriver():
    def __init__(self, regs, name):
        self.regs = regs
        self.name = name
        self.build()

    def build(self):
        for key, value in self.regs.d.items():
            if self.name in key:
                key = key.replace(self.name + "_", "")
                setattr(self, key, value)

    def write(self, value):
        self.o.write(value)

    def read(self):
        return self.i.read()
