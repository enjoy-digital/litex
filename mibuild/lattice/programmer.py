import os
import subprocess

from mibuild.generic_programmer import GenericProgrammer
from mibuild import tools

# XXX Lattice programmer need an .xcf file, will need clean up and support for more parameters
_xcf_template = """
<?xml version='1.0' encoding='utf-8' ?>
<!DOCTYPE        ispXCF    SYSTEM    "IspXCF.dtd" >
<ispXCF version="3.4.1">
    <Comment></Comment>
    <Chain>
        <Comm>JTAG</Comm>
        <Device>
            <SelectedProg value="TRUE"/>
            <Pos>1</Pos>
            <Vendor>Lattice</Vendor>
            <Family>LatticeECP3</Family>
            <Name>LFE3-35EA</Name>
            <File>{bitstream_file}</File>
            <Operation>Fast Program</Operation>
        </Device>
    </Chain>
    <ProjectOptions>
        <Program>SEQUENTIAL</Program>
        <Process>ENTIRED CHAIN</Process>
        <OperationOverride>No Override</OperationOverride>
        <StartTAP>TLR</StartTAP>
        <EndTAP>TLR</EndTAP>
        <VerifyUsercode value="FALSE"/>
    </ProjectOptions>
    <CableOptions>
        <CableName>USB2</CableName>
        <PortAdd>FTUSB-0</PortAdd>
        <USBID>Dual RS232-HS A Location 0000 Serial A</USBID>
        <JTAGPinSetting>
            TRST    ABSENT;
            ISPEN    ABSENT;
        </JTAGPinSetting>
    </CableOptions>
</ispXCF>
"""


class LatticeProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def load_bitstream(self, bitstream_file):
        xcf_file = bitstream_file.replace(".bit", ".xcf")
        xcf_content = _xcf_template.format(bitstream_file=bitstream_file)
        tools.write_to_file(xcf_file, xcf_content)
        subprocess.call(["pgrcmd", "-infile", xcf_file])
