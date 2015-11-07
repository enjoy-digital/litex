from collections import OrderedDict, namedtuple

from migen.fhdl.structure import *
from migen.fhdl.namer import build_namespace
from migen.fhdl.tools import list_special_ios
from migen.fhdl.structure import _Fragment
from migen.fhdl.conv_output import ConvOutput


_Port = namedtuple("_Port", "name direction")
_Cell = namedtuple("_Cell", "name ports")
_Property = namedtuple("_Property", "name value")
_Instance = namedtuple("_Instance", "name cell properties")
_NetBranch = namedtuple("_NetBranch", "portname instancename")


def _write_cells(cells):
    r = ""
    for cell in cells:
        r += """
        (cell {0.name}
            (cellType GENERIC)
                (view view_1
                    (viewType NETLIST)
                    (interface""".format(cell)
        for port in cell.ports:
            r += """
                        (port {0.name} (direction {0.direction}))""".format(port)
        r += """
                    )
                )
        )"""
    return r


def _write_io(ios):
    r = ""
    for s in ios:
        r += """
                        (port {0.name} (direction {0.direction}))""".format(s)
    return r


def _write_instantiations(instances, cell_library):
    instantiations = ""
    for instance in instances:
        instantiations += """
                        (instance {0.name}
                            (viewRef view_1 (cellRef {0.cell} (libraryRef {1})))""".format(instance, cell_library)
        for prop in instance.properties:
            instantiations += """
                            (property {0} (string "{1}"))""".format(prop.name, prop.value)
        instantiations += """
                        )"""
    return instantiations


def _write_connections(connections):
    r = ""
    for netname, branches in connections.items():
        r += """
                        (net {0}
                            (joined""".format(netname)
        for branch in branches:
            r += """
                                (portRef {0}{1})""".format(branch.portname, "" if branch.instancename == "" else " (instanceRef {})".format(branch.instancename))
        r += """
                            )
                        )"""
    return r


def _write_edif(cells, ios, instances, connections, cell_library, design_name, part, vendor):
    r = """(edif {0}
    (edifVersion 2 0 0)
    (edifLevel 0)
    (keywordMap (keywordLevel 0))
    (external {1}
        (edifLevel 0)
        (technology (numberDefinition))""".format(design_name, cell_library)
    r += _write_cells(cells)
    r += """
    )
    (library {0}_lib
        (edifLevel 0)
        (technology (numberDefinition))
        (cell {0}
            (cellType GENERIC)
                (view view_1
                    (viewType NETLIST)
                    (interface""".format(design_name)
    r += _write_io(ios)
    r += """
                        (designator "{0}")
                    )
                    (contents""".format(part)
    r += _write_instantiations(instances, cell_library)
    r += _write_connections(connections)
    r += """
                    )
                )
        )
    )
    (design {0}
        (cellRef {0} (libraryRef {0}_lib))
        (property PART (string "{1}") (owner "{2}"))
    )
)""".format(design_name, part, vendor)

    return r


def _generate_cells(f):
    cell_dict = OrderedDict()
    for special in f.specials:
        if isinstance(special, Instance):
            port_list = []
            for port in special.items:
                if isinstance(port, Instance.Input):
                    port_list.append(_Port(port.name, "INPUT"))
                elif isinstance(port, Instance.Output):
                    port_list.append(_Port(port.name, "OUTPUT"))
                elif isinstance(port, Instance.InOut):
                    port_list.append(_Port(port.name, "INOUT"))
                elif isinstance(port, Instance.Parameter):
                    pass
                else:
                    raise NotImplementedError("Unsupported instance item")
            if special.of in cell_dict:
                if set(port_list) != set(cell_dict[special.of]):
                    raise ValueError("All instances must have the same ports for EDIF conversion")
            else:
                cell_dict[special.of] = port_list
        else:
            raise ValueError("EDIF conversion can only handle synthesized fragments")
    return [_Cell(k, v) for k, v in cell_dict.items()]


def _generate_instances(f, ns):
    instances = []
    for special in f.specials:
        if isinstance(special, Instance):
            props = []
            for prop in special.items:
                if isinstance(prop, Instance.Input):
                    pass
                elif isinstance(prop, Instance.Output):
                    pass
                elif isinstance(prop, Instance.InOut):
                    pass
                elif isinstance(prop, Instance.Parameter):
                    props.append(_Property(name=prop.name, value=prop.value))
                else:
                    raise NotImplementedError("Unsupported instance item")
            instances.append(_Instance(name=ns.get_name(special), cell=special.of, properties=props))
        else:
            raise ValueError("EDIF conversion can only handle synthesized fragments")
    return instances


def _generate_ios(f, ios, ns):
    outs = list_special_ios(f, False, True, False)
    inouts = list_special_ios(f, False, False, True)
    r = []
    for io in ios:
        direction = "OUTPUT" if io in outs else "INOUT" if io in inouts else "INPUT"
        r.append(_Port(name=ns.get_name(io), direction=direction))
    return r


def _generate_connections(f, ios, ns):
    r = OrderedDict()
    for special in f.specials:
        if isinstance(special, Instance):
            instname = ns.get_name(special)
            for port in special.items:
                if isinstance(port, Instance._IO):
                    s = ns.get_name(port.expr)
                    if s not in r:
                        r[s] = []
                    r[s].append(_NetBranch(portname=port.name, instancename=instname))
                elif isinstance(port, Instance.Parameter):
                    pass
                else:
                    raise NotImplementedError("Unsupported instance item")
        else:
            raise ValueError("EDIF conversion can only handle synthesized fragments")
    for s in ios:
        io = ns.get_name(s)
        if io not in r:
            r[io] = []
        r[io].append(_NetBranch(portname=io, instancename=""))
    return r


def convert(f, ios, cell_library, vendor, device, name="top"):
    if not isinstance(f, _Fragment):
        f = f.get_fragment()
    if f.comb != [] or f.sync != {}:
        raise ValueError("EDIF conversion can only handle synthesized fragments")
    if ios is None:
        ios = set()
    cells = _generate_cells(f)
    ns = build_namespace(list_special_ios(f, True, True, True))
    instances = _generate_instances(f, ns)
    inouts = _generate_ios(f, ios, ns)
    connections = _generate_connections(f, ios, ns)
    src = _write_edif(cells, inouts, instances, connections, cell_library, name, device, vendor)

    r = ConvOutput()
    r.set_main_source(src)
    r.ns = ns
    return r
