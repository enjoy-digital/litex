import time
from misoclib.tools.litescope.software.driver.la import LiteScopeLADriver


def main(wb):
    la = LiteScopeLADriver(wb.regs, "la", debug=True)

    wb.open()
    regs = wb.regs
    # # #
    conditions = {}
    la.configure_term(port=0, cond=conditions)
    la.configure_sum("term")
    # Run Logic Analyzer
    la.run(offset=2048, length=4000)

    while not la.done():
        pass

    la.upload()
    la.save("dump.vcd")
    # # #
    wb.close()
