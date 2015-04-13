from misoclib.tools.litescope.host.driver.la import LiteScopeLADriver


def main(wb):
    wb.open()
    ###
    la = LiteScopeLADriver(wb.regs, "la", debug=True)

    #cond = {"cnt0"    :    128} # trigger on cnt0 = 128
    cond = {}  # trigger on cnt0 = 128
    la.configure_term(port=0, cond=cond)
    la.configure_sum("term")
    la.configure_subsampler(1)
    #la.configure_qualifier(1)
    la.configure_rle(1)
    la.run(offset=128, length=256)

    while not la.done():
        pass
    la.upload()

    la.save("dump.vcd")
    la.save("dump.csv")
    la.save("dump.py")
    la.save("dump.sr")
    ###
    wb.close()
