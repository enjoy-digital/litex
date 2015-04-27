import random

def randn(max_n):
    return random.randint(0, max_n-1)


class RandRun:
    def __init__(self, level=0):
        self.run = True
        self.level = level

    def do_simulation(self, selfp):
        self.run = True
        n = randn(100)
        if n < self.level:
            self.run = False
