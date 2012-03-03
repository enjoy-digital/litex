import socket
import os

#
# Message classes
#

class Message:
	def __init__(self, *pvalues):
		for parameter, value in zip(self.parameters, pvalues):
			assert(isinstance(value, parameter[0]))
			setattr(self, parameter[1], value)

class MessageTick(Message):
	code = 0
	parameters = []

class MessageGo(Message):
	code = 1
	parameters = []

class MessageWrite(Message):
	code = 2
	parameters = [(str, "signal"), (int, "value")]

class MessageRead(Message):
	code = 3
	parameters = [(str, "signal")]

class MessageReadReply(Message):
	code = 4
	parameters = [(int, "value")]

message_classes = [MessageTick, MessageGo, MessageWrite, MessageRead, MessageReadReply]

#
# Packing
#

def _pack_int(v):
	# TODO
	return []

def _pack_str(v):
	# TODO
	return []

def _pack(message):
	r = [message.code]
	for p, t in message.parameters:
		value = getattr(message, p)
		assert(isinstance(value, t))
		if t == int:
			r += _pack_int(value)
		elif t == str:
			r += _pack_str(value)
		else:
			raise TypeError
	return bytes(r)

#
# Unpacking
#

def _unpack_int(i):
	# TODO
	return 0

def _unpack_str(i):
	# TODO
	return ""

def _unpack(message):
	i = iter(message)
	code = next(i)
	msgclass = next(filter(lambda x: x.code == code, message_classes))
	pvalues = []
	for p, t in msgclass.parameters:
		if t == int:
			v = _unpack_int(i)
		elif t == str:
			v = _unpack_str(i)
		else:
			raise TypeError
		pvalues.append(v)
	return msgclass(*pvalues)

#
# I/O
#

class PacketTooLarge(Exception):
	pass
	
class Initiator:
	def __init__(self, sockaddr="simsocket"):
		self.sockaddr = sockaddr
		self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
		self._cleanup_file()
		self.socket.bind(self.sockaddr)
		self.socket.listen(1)
	
	def _cleanup_file(self):
		try:
			os.remove(self.sockaddr)
		except OSError:
			pass
	
	def accept(self):
		self.conn, addr = self.socket.accept()
	
	def send(self, message):
		self.conn.send(_pack(message))
	
	def recv(self):
		maxlen = 4096
		packet = self.conn.recv(maxlen)
		if len(packet) >= maxlen:
			raise PacketTooLarge
		return _unpack(packet)

	def __del__(self):
		if hasattr(self, "conn"):
			self.conn.close()
		if hasattr(self, "socket"):
			self.socket.close()
		self._cleanup_file()
