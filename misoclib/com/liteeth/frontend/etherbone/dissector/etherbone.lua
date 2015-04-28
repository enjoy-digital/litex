-- Etherbone Dissector
-- Copyright 2013 OHWR.org
-- Copyright 2015 EnjoyDigital (global clean up)

local bit = require("bit")

local VALS_BOOL = {[0] = "False", [1] = "True"}
local VALS_RES = {[0] = "not set", [1] = "set, bad data?"}
local VALS_SIZE = {
[0x00] = "Bad Value",
[0x01] = "8 bit",
[0x02] = "16 bit",
[0x03] = "16,8 bit",
[0x04] = "32 bit",
[0x05] = "32,8 bit",
[0x06] = "32,16 bit",
[0x07] = "32,16,8 bit",
[0x08] = "64 bit",
[0x09] = "64,8 bit",
[0x0A] = "64,16 bit",
[0x0B] = "64,16,8 bit",
[0x0C] = "64,32 bit",
[0x0D] = "64,32,8 bit",
[0x0E] = "64,32,16 bit",
[0x0F] = "64,32,16,8 bit",
}

function num2hex(num)
    local hexstr = '0123456789abcdef'
    local s = ''
    while num > 0 do
        local mod = math.fmod(num, 16)
        s = string.sub(hexstr, mod+1, mod+1) .. s
        num = math.floor(num / 16)
    end
    if s == '' then s = '0' end
    return s
end

function max(a, b)
  if a > b then
    return a
  else
    return b
  end
end

-- declare protocol
proto_eb = Proto("eb", "Etherbone")

-- declare fields
local eb = proto_eb.fields
eb.hdr = ProtoField.uint32("eb.hdr", "Header", base.HEX)
eb.rec = ProtoField.bytes("eb.rec",  "Record	", base.HEX)

eb.hdr_magic 		= ProtoField.uint16("eb.hdr.magic",		"Magic         ", base.HEX, nil, 0xFFFF)
eb.hdr_ver 			= ProtoField.uint16("eb.hdr.ver",		"Version       ", base.DEC, nil, 0xF000)
eb.hdr_noreads 		= ProtoField.uint16("eb.hdr.noreads",	"No Reads      ", base.DEC, VALS_BOOL, 0x0400)
eb.hdr_proberep 	= ProtoField.uint16("eb.hdr.proberes",	"Probe Reply   ", base.DEC, VALS_BOOL, 0x0200)
eb.hdr_probereq 	= ProtoField.uint16("eb.hdr.probereq",	"Probe Flag    ", base.DEC, VALS_BOOL, 0x0100)
eb.hdr_adrs 		= ProtoField.uint16("eb.hdr.adrw",		"Address Width ", base.DEC, VALS_SIZE , 0x00F0)
eb.hdr_ports 		= ProtoField.uint16("eb.hdr.portw",		"Port    Width ", base.DEC, VALS_SIZE , 0x000F)

eb.rec_hdr			= ProtoField.uint32("eb.rec.hdr",		"Header ", base.HEX)
eb.rec_writes		= ProtoField.bytes("eb.rec.writes",		"Writes ", base.HEX)
eb.rec_reads		= ProtoField.bytes("eb.rec.reads",		"Reads  ", base.HEX)

eb.rec_hdr_flags	= ProtoField.uint8("eb.rec.hdr.flags",		"Flags  ", base.HEX)
eb.rec_hdr_select 	= ProtoField.uint8("eb.rec.hdr.select",		"Select ", base.HEX)
eb.rec_hdr_wr	 	= ProtoField.uint8("eb.rec.hdr.wr",			"Writes ", base.DEC)
eb.rec_hdr_rd	 	= ProtoField.uint8("eb.rec.hdr.rd",			"Reads  ", base.DEC)

eb.rec_hdr_flags_adrcfg = ProtoField.uint8("eb.rec.hdr.flags.adrcfg",	"ReplyToCfgSpace  ", base.DEC, VALS_BOOL, 0x80)
eb.rec_hdr_flags_rbacfg = ProtoField.uint8("eb.rec.hdr.adrcfg",			"ReadFromCfgSpace ", base.DEC, VALS_BOOL, 0x40)
eb.rec_hdr_flags_rdfifo = ProtoField.uint8("eb.rec.hdr.adrcfg",			"ReadFIFO         ", base.DEC, VALS_BOOL, 0x20)
eb.rec_hdr_flags_dropcyc= ProtoField.uint8("eb.rec.hdr.adrcfg",			"DropCycle        ", base.DEC, VALS_BOOL, 0x08)
eb.rec_hdr_flags_wbacfg = ProtoField.uint8("eb.rec.hdr.adrcfg",			"WriteToCfgSpace  ", base.DEC, VALS_BOOL, 0x04)
eb.rec_hdr_flags_wrfifo = ProtoField.uint8("eb.rec.hdr.adrcfg",			"WriteFIFO        ", base.DEC, VALS_BOOL, 0x02)

eb.rec_wrsadr8	= ProtoField.uint8("eb.rec.wrsadr8",			"BaseAddr8  ", base.HEX)
eb.rec_wrsadr16	= ProtoField.uint16("eb.rec.wrsadr16",			"BaseAddr16 ", base.HEX)
eb.rec_wrsadr32	= ProtoField.uint32("eb.rec.wrsadr32",			"BaseAddr32 ", base.HEX)
eb.rec_wrsadr64	= ProtoField.uint64("eb.rec.wrsadr64",			"BaseAddr64 ", base.HEX)
eb.rec_wrdata8	= ProtoField.uint8("eb.rec.wrdata8",			"Value8     ", base.HEX)
eb.rec_wrdata16	= ProtoField.uint16("eb.rec.wrdata16",			"Value16    ", base.HEX)
eb.rec_wrdata32	= ProtoField.uint32("eb.rec.wrdata32",			"Value32    ", base.HEX)
eb.rec_wrdata64	= ProtoField.uint64("eb.rec.wrdata64",			"Value64    ", base.HEX)

eb.rec_rdbadr8	= ProtoField.uint8("eb.rec.rdbadr8",			"ReplyAddr8  ", base.HEX)
eb.rec_rdbadr16	= ProtoField.uint16("eb.rec.rdbadr16",			"ReplyAddr16 ", base.HEX)
eb.rec_rdbadr32	= ProtoField.uint32("eb.rec.rdbadr32",			"ReplyAddr32 ", base.HEX)
eb.rec_rdbadr64	= ProtoField.uint64("eb.rec.rdbadr64",			"ReplyAddr64 ", base.HEX)
eb.rec_rddata8	= ProtoField.uint8("eb.rec.rddata8",			"Address8    ", base.HEX)
eb.rec_rddata16	= ProtoField.uint16("eb.rec.rddata16",			"Address16   ", base.HEX)
eb.rec_rddata32	= ProtoField.uint32("eb.rec.rddata32",			"Address32   ", base.HEX)
eb.rec_rddata64	= ProtoField.uint64("eb.rec.rddata64",			"Address64   ", base.HEX)

-- define the dissector
function proto_eb.dissector(buf, pinfo, tree)
		if (buf:len() < 4) then
			return 0 -- too short, go to default protocol
		end

		local mylen = buf:len()
		pinfo.cols.protocol = "eb"

		-- add packet to the tree root, fields will be added to subtree
		local t = tree:add( proto_eb, buf(0, mylen) )
		local t_hdr = t:add( eb.hdr, buf(0,4) )

		local magic = num2hex(tonumber(buf(0,2):uint()))
		if(magic == "4e6f") then

			t_hdr:add( eb.hdr_magic,	buf(0,2))	-- magic
			t_hdr:add( eb.hdr_ver,		buf(2,2))	-- version
			t_hdr:add( eb.hdr_noreads,	buf(2,2))	-- no reads
			t_hdr:add( eb.hdr_proberep,	buf(2,2))	-- probe response
			t_hdr:add( eb.hdr_probereq,	buf(2,2))	-- probe request

			t_hdr:add( eb.hdr_adrs,		buf(2,2))	-- supported addr size
			t_hdr:add( eb.hdr_ports,	buf(2,2))	-- supported port size

			local probe = tonumber(buf(2,1):uint()) % 4
			if (probe == 0) then
				local widths = tonumber(buf(3,1):uint())
				local data_width = widths % 16
				local addr_width = (widths - data_width) / 16
				local alignment = max(max(addr_width, data_width), 2)

				local record_alignment = max(alignment, 4)
				local offset = max(alignment, 4)

				local recordcnt = 0
				while (offset < buf:len()) do
					local wr = tonumber(buf(offset+2,1):uint())
					local rd = tonumber(buf(offset+3,1):uint())

					local rdadr = 0
					local wradr = 0
					if(rd > 0) then
						rdadr = 1
					end
					if(wr > 0) then
						wradr = 1
					end

					if((wr == 0) and (rd == 0)) then
						offset = offset + record_alignment
					else
						local t_rec = t:add( "Record "..tostring(recordcnt).."  (W"..tostring(wr).." R"..tostring(rd)..")", buf(offset, (record_alignment+(rd+wr+rdadr+wradr)*alignment)))
						recordcnt = recordcnt + 1

						local t_rec_hdr = t_rec:add( eb.rec_hdr, buf(offset,4))
						local t_rec_hdr_flags = t_rec_hdr:add( eb.rec_hdr_flags, buf(offset,1))
						t_rec_hdr_flags:add( eb.rec_hdr_flags_adrcfg, buf(offset,1))
						t_rec_hdr_flags:add( eb.rec_hdr_flags_rbacfg, buf(offset,1))
						t_rec_hdr_flags:add( eb.rec_hdr_flags_rdfifo, buf(offset,1))
						t_rec_hdr_flags:add( eb.rec_hdr_flags_dropcyc , buf(offset,1))
						t_rec_hdr_flags:add( eb.rec_hdr_flags_wbacfg , buf(offset,1))
						t_rec_hdr_flags:add( eb.rec_hdr_flags_wrfifo, buf(offset,1))
						t_rec_hdr:add( eb.rec_hdr_select, buf(offset+1,1))
						t_rec_hdr:add( eb.rec_hdr_wr, buf(offset+2,1))
						t_rec_hdr:add( eb.rec_hdr_rd, buf(offset+3,1))
						offset = offset + record_alignment
						local tmp_offset

						if(wr > 0) then
							local t_writes = t_rec:add( eb.rec_writes, buf(offset,(1+wr)*alignment))

							if     addr_width==1 then t_writes:add(eb.rec_wrsadr8,  buf(offset+alignment-1, 1))
							elseif addr_width==2 then t_writes:add(eb.rec_wrsadr16, buf(offset+alignment-2, 2))
							elseif addr_width==4 then t_writes:add(eb.rec_wrsadr32, buf(offset+alignment-4, 4))
							elseif addr_width==8 then t_writes:add(eb.rec_wrsadr64, buf(offset+alignment-8, 8))
							end
							offset = offset + alignment

							tmp_offset = offset
							while (tmp_offset < offset+wr*alignment) do
								if     data_width==1 then t_writes:add( eb.rec_wrdata8,  buf(tmp_offset+alignment-1, 1))
								elseif data_width==2 then t_writes:add( eb.rec_wrdata16, buf(tmp_offset+alignment-2, 2))
								elseif data_width==4 then t_writes:add( eb.rec_wrdata32, buf(tmp_offset+alignment-4, 4))
								elseif data_width==8 then t_writes:add( eb.rec_wrdata64, buf(tmp_offset+alignment-8, 8))
								end
								tmp_offset = tmp_offset + alignment
							end
							offset = tmp_offset
						end

						if(rd > 0) then
							local t_reads = t_rec:add( eb.rec_reads, buf(offset,(1+rd)*alignment))

							if     addr_width==1 then t_reads:add( eb.rec_rdbadr8,  buf(offset+alignment-1, 1))
							elseif addr_width==2 then t_reads:add( eb.rec_rdbadr16, buf(offset+alignment-2, 2))
							elseif addr_width==4 then t_reads:add( eb.rec_rdbadr32, buf(offset+alignment-4, 4))
							elseif addr_width==8 then t_reads:add( eb.rec_rdbadr64, buf(offset+alignment-8, 8))
							end
							offset = offset + alignment

							tmp_offset = offset
							while (tmp_offset < offset+rd*alignment) do
								if     addr_width==1 then t_reads:add( eb.rec_rddata8,  buf(tmp_offset+alignment-1, 1))
								elseif addr_width==2 then t_reads:add( eb.rec_rddata16, buf(tmp_offset+alignment-2, 2))
								elseif addr_width==4 then t_reads:add( eb.rec_rddata32, buf(tmp_offset+alignment-4, 4))
								elseif addr_width==8 then t_reads:add( eb.rec_rddata64, buf(tmp_offset+alignment-8, 8))
								end
								tmp_offset = tmp_offset + alignment
							end
							offset = tmp_offset
						end
					end
				end

			end

		else
			return 0
		end

end

-- register eb protocol on UDP port 20000
local tab = DissectorTable.get("udp.port")
tab:add(20000, proto_eb)
