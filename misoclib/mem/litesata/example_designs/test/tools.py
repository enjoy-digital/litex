from misoclib.tools.litescope.software.dump import *

primitives = {
    "ALIGN":  0x7B4A4ABC,
    "CONT":   0X9999AA7C,
    "SYNC":   0xB5B5957C,
    "R_RDY":  0x4A4A957C,
    "R_OK":   0x3535B57C,
    "R_ERR":  0x5656B57C,
    "R_IP":   0X5555B57C,
    "X_RDY":  0x5757B57C,
    "CONT":   0x9999AA7C,
    "WTRM":   0x5858B57C,
    "SOF":    0x3737B57C,
    "EOF":    0xD5D5B57C,
    "HOLD":   0xD5D5AA7C,
    "HOLDA":  0X9595AA7C
}


def decode_primitive(dword):
    for k, v in primitives.items():
        if dword == v:
            return k
    return ""


def link_trace(la, tx_data_name, rx_data_name):
    r = ""
    dump = Dump()
    dump.add_from_layout(la.layout, la.data)

    for var in dump.vars:
        if var.name == tx_data_name:
            tx_data = var.values
        if var.name == rx_data_name:
            rx_data = var.values

    for i in range(len(tx_data)):
        tx = "{:08x} ".format(tx_data[i])
        tx += decode_primitive(tx_data[i])
        tx += " "*(16-len(tx))

        rx = "{:08x} ".format(rx_data[i])
        rx += decode_primitive(rx_data[i])
        rx += " "*(16-len(rx))

        r += tx + rx + "\n"

    return r
