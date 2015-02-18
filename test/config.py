use_uart = 0
use_eth = 1

csr_csv_file = "./csr.csv"
busword = 32
debug_wb = False

if use_uart:
	from litescope.host.driver.uart import LiteScopeUARTDriver
	wb = LiteScopeUART2WBDriver(2, 921600, csr_csv_file, busword, debug_wb)

if use_eth:
	from litescope.host.driver.etherbone import LiteScopeEtherboneDriver
	wb = LiteScopeEtherboneDriver("192.168.1.40", 20000, csr_csv_file, debug_wb)
