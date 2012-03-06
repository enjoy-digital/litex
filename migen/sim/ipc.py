import socket
import os

#
# Message classes
#

class Int32(int):
	pass

class Message:
	def __init__(self, *pvalues):
		for parameter, value in zip(self.parameters, pvalues):
			assert(isinstance(value, parameter[0]))
			setattr(self, parameter[1], value)
	
	def __str__(self):
		p = ""
		for parameter in self.parameters:
			p += parameter[1] + "=" + str(getattr(self, parameter[1]))
		if p:
			p = " " + p
		return "<" + self.__class__.__name__ + p + ">"

class MessageTick(Message):
	code = 0
	parameters = []

class MessageGo(Message):
	code = 1
	parameters = []

class MessageWrite(Message):
	code = 2
	parameters = [(str, "name"), (Int32, "index"), (int, "value")]

class MessageRead(Message):
	code = 3
	parameters = [(str, "name"), (Int32, "index")]

class MessageReadReply(Message):
	code = 4
	parameters = [(int, "value")]

message_classes = [MessageTick, MessageGo, MessageWrite, MessageRead, MessageReadReply]

#
# Packing
#

def _pack_int(v):
	p = []
	while v != 0:
		p.append(v & 0xff)
		v >>= 8
	p.insert(0, len(p))
	return p

def _pack_str(v):
	p = [ord(c) for c in v]
	p.append(0)
	return p

def _pack_int32(v):
	return [
		v & 0xff,
		(v & 0xff00) >> 8,
		(v & 0xff0000) >> 16,
		(v & 0xff000000) >> 24
	]

def _pack(message):
	r = [message.code]
	for t, p in message.parameters:
		value = getattr(message, p)
		assert(isinstance(value, t))
		if t == int:
			r += _pack_int(value)
		elif t == str:
			r += _pack_str(value)
		elif t == Int32:
			r += _pack_int32(value)
		else:
			raise TypeError
	return bytes(r)

#
# Unpacking
#

def _unpack_int(i, nchunks=None):
	v = 0
	power = 1
	if nchunks is None:
		nchunks = next(i)
	for j in range(nchunks):
		v += power*next(i)
		power *= 256
	return v

def _unpack_str(i):
	v = ""
	c = next(i)
	while c:
		v += chr(c)
		c = next(i)
	return v

def _unpack(message):
	i = iter(message)
	code = next(i)
	msgclass = next(filter(lambda x: x.code == code, message_classes))
	pvalues = []
	for t, p in msgclass.parameters:
		if t == int:
			v = _unpack_int(i)
		elif t == str:
			v = _unpack_str(i)
		elif t == Int32:
			v = _unpack_int(i, 4)
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
	def __init__(self, sockaddr):
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
		maxlen = 2048
		packet = self.conn.recv(maxlen)
		if len(packet) < 1:
			return None
		if len(packet) >= maxlen:
			raise PacketTooLarge
		return _unpack(packet)

	def __del__(self):
		if hasattr(self, "conn"):
			self.conn.shutdown(socket.SHUT_RDWR)
			self.conn.close()
		if hasattr(self, "socket"):
			self.socket.shutdown(socket.SHUT_RDWR)
			self.socket.close()
		self._cleanup_file()
