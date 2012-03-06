import inspect
from opcode import opname

def get_var_name(frame):
	code = frame.f_code
	call_index = frame.f_lasti
	if opname[code.co_code[call_index]] != "CALL_FUNCTION":
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
		elif opc == "LOAD_GLOBAL" or opc == "LOAD_ATTR" or opc == "LOAD_FAST":
			index += 3
		elif opc == "DUP_TOP":
			index += 1
		else:
			return None

def trace_back(name=None):
	l = []
	frame = inspect.currentframe().f_back.f_back
	while frame is not None:
		try:
			obj = frame.f_locals["self"]
		except KeyError:
			obj = None
		if obj is not None and hasattr(obj, "__del__"):
			obj = None
		if obj is None:
			modules = frame.f_globals["__name__"]
			modules = modules.split(".")
			obj = modules[len(modules)-1]
		
		if name is None:
			name = get_var_name(frame)
		l.insert(0, (obj, name))
		name = None
		frame = frame.f_back
	return l
