import sys
from bist import *
from misoclib.tools.litescope.software.driver.la import LiteScopeLADriver


def main(wb):
    identifys = []
    generators = []
    checkers = []
    for i in range(4):
        identifys.append(LiteSATABISTIdentifyDriver(wb.regs, "sata_bist{:d}".format(i)))
        generators.append(LiteSATABISTGeneratorDriver(wb.regs, "sata_bist{:d}".format(i)))
        checkers.append(LiteSATABISTCheckerDriver(wb.regs, "sata_bist{:d}".format(i)))

    wb.open()
    regs = wb.regs
    # # #

    print("Identify HDDs:")
    print("-"*80)
    for i, identify in enumerate(identifys):
        identify.run()
        print("HDD{:d}:".format(i))
        print("-"*40)
        identify.hdd_info()
        print("")

    print("Test Mirroring:")
    print("-"*80)
    errors = 0
    for sector in range(8):
        # Write with one generator, verify with all checkers.
        # Use generator number as sector offset to ensure we
        # are not reading data written by another generator.
        for offset, generator in enumerate(generators):
            generator.run(sector + offset, 1024, 1, 1)
            for checker in checkers:
                a, e, s = checker.run(sector + offset, 1024, 1, 1)
                errors += e
    print("errors {:d}".format(errors))

    # # #
    wb.close()
