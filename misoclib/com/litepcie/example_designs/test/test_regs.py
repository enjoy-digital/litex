def main(wb):
    wb.open()
    regs = wb.regs
    # # #
    print("sysid     : 0x{:04x}".format(regs.identifier_sysid.read()))
    print("revision  : 0x{:04x}".format(regs.identifier_revision.read()))
    print("frequency : {}MHz".format(int(regs.identifier_frequency.read()/1000000)))
    print("link up   : {}".format(regs.pcie_phy_lnk_up.read()))
    print("bus_master_enable : {}".format(regs.pcie_phy_bus_master_enable.read()))
    print("msi_enable : {}".format(regs.pcie_phy_msi_enable.read()))
    print("max_req_request_size : {}".format(regs.pcie_phy_max_request_size.read()))
    print("max_payload_size : {}".format(regs.pcie_phy_max_payload_size.read()))
    # # #
    wb.close()
