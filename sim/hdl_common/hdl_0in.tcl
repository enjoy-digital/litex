set HDL_TOOLTYPE SIMULATION
set HDL_TOOLNAME 0in
set HDL_PUTS puts
set HDL_MSG_FORMAT "********** %s **********"

proc hdl_tool_library {lib} {
}

proc hdl_tool_compile {format version incdirs library define files behavioral} {
   set command analyze
   lappend command -work [string tolower $library]
   switch $format {
      "vhdl" {
         lappend command -vhdl
      }
      "verilog" {
         foreach d $define {
            lappend command +define+$d
         }
         foreach i $incdirs {
            lappend command +incdir+$i
         }
      }
   }
   foreach f $files {
      lappend command $f
   }
   puts [eval $command]
}   
