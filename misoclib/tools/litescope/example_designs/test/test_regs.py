def main(wb):
    wb.open()
    regs = wb.regs
    # # #
    print("sysid     : 0x{:04x}".format(regs.identifier_sysid.read()))
    print("revision  : 0x{:04x}".format(regs.identifier_revision.read()))
    print("frequency : {}MHz".format(int(regs.identifier_frequency.read()/1000000)))
    # # #
    wb.close()
