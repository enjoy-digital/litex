from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac import LiteEthMAC
from misoclib.com.liteeth.core.arp import LiteEthARP
from misoclib.com.liteeth.core.ip import LiteEthIP
from misoclib.com.liteeth.core.udp import LiteEthUDP
from misoclib.com.liteeth.core.icmp import LiteEthICMP


class LiteEthIPCore(Module, AutoCSR):
    def __init__(self, phy, mac_address, ip_address, clk_freq, with_icmp=True):
        self.submodules.mac = LiteEthMAC(phy, 8, interface="crossbar", with_preamble_crc=True)
        self.submodules.arp = LiteEthARP(self.mac, mac_address, ip_address, clk_freq)
        self.submodules.ip = LiteEthIP(self.mac, mac_address, ip_address, self.arp.table)
        if with_icmp:
        	self.submodules.icmp = LiteEthICMP(self.ip, ip_address)


class LiteEthUDPIPCore(LiteEthIPCore):
    def __init__(self, phy, mac_address, ip_address, clk_freq, with_icmp=True):
        LiteEthIPCore.__init__(self, phy, mac_address, ip_address, clk_freq, with_icmp)
        self.submodules.udp = LiteEthUDP(self.ip, ip_address)
