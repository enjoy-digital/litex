import inspect
from opcode import opname
from collections import defaultdict


def get_var_name(frame):
    code = frame.f_code
    call_index = frame.f_lasti
    call_opc = opname[code.co_code[call_index]]
    if call_opc != "CALL_FUNCTION" and call_opc != "CALL_FUNCTION_VAR":
        return None
    index = call_index+3
    while True:
        opc = opname[code.co_code[index]]
        if opc == "STORE_NAME" or opc == "STORE_ATTR":
            name_index = int(code.co_code[index+1])
            return code.co_names[name_index]
        elif opc == "STORE_FAST":
            name_index = int(code.co_code[index+1])
            return code.co_varnames[name_index]
        elif opc == "STORE_DEREF":
            name_index = int(code.co_code[index+1])
            return code.co_cellvars[name_index]
        elif opc == "LOAD_GLOBAL" or opc == "LOAD_ATTR" or opc == "LOAD_FAST" or opc == "LOAD_DEREF":
            index += 3
        elif opc == "DUP_TOP":
            index += 1
        elif opc == "BUILD_LIST":
            index += 3
        else:
            return None


def remove_underscore(s):
    if len(s) > 2 and s[0] == "_" and s[1] != "_":
        s = s[1:]
    return s


def get_obj_var_name(override=None, default=None):
    if override:
        return override

    frame = inspect.currentframe().f_back
    # We can be called via derived classes. Go back the stack frames
    # until we reach the first class that does not inherit from us.
    ourclass = frame.f_locals["self"].__class__
    while "self" in frame.f_locals and isinstance(frame.f_locals["self"], ourclass):
        frame = frame.f_back

    vn = get_var_name(frame)
    if vn is None:
        vn = default
    else:
        vn = remove_underscore(vn)
    return vn

name_to_idx = defaultdict(int)
classname_to_objs = dict()


def index_id(l, obj):
    for n, e in enumerate(l):
        if id(e) == id(obj):
            return n
    raise ValueError


def trace_back(varname=None):
    l = []
    frame = inspect.currentframe().f_back.f_back
    while frame is not None:
        if varname is None:
            varname = get_var_name(frame)
        if varname is not None:
            varname = remove_underscore(varname)
            l.insert(0, (varname, name_to_idx[varname]))
            name_to_idx[varname] += 1

        try:
            obj = frame.f_locals["self"]
        except KeyError:
            obj = None
        if hasattr(obj, "__del__"):
            obj = None

        if obj is None:
            if varname is not None:
                coname = frame.f_code.co_name
                if coname == "<module>":
                    modules = frame.f_globals["__name__"]
                    modules = modules.split(".")
                    coname = modules[len(modules)-1]
                coname = remove_underscore(coname)
                l.insert(0, (coname, name_to_idx[coname]))
                name_to_idx[coname] += 1
        else:
            classname = obj.__class__.__name__.lower()
            try:
                objs = classname_to_objs[classname]
            except KeyError:
                classname_to_objs[classname] = [obj]
                idx = 0
            else:
                try:
                    idx = index_id(objs, obj)
                except ValueError:
                    idx = len(objs)
                    objs.append(obj)
            classname = remove_underscore(classname)
            l.insert(0, (classname, idx))

        varname = None
        frame = frame.f_back
    return l
