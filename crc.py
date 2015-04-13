import binascii


def insert_crc(i_filename, fbi_mode=False, o_filename=None):
    if o_filename is None:
        o_filename = i_filename

    with open(i_filename, 'rb') as f:
        fdata = f.read()
    fcrc = binascii.crc32(fdata).to_bytes(4, byteorder="big")
    flength = len(fdata).to_bytes(4, byteorder="big")

    with open(o_filename, 'wb') as f:
        if fbi_mode:
            f.write(flength)
            f.write(fcrc)
            f.write(fdata)
        else:
            f.write(fdata)
            f.write(fcrc)
