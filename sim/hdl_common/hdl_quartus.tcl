set HDL_TOOLTYPE SYNTHESIS
set HDL_TOOLNAME QuartusII
set HDL_PUTS puts
set HDL_MSG_FORMAT "********** %s **********"


proc hdl_tool_library {lib_list} {
}

proc hdl_tool_compile {format version incdirs library define files behavioral} {
   #if {[llength $incdirs]} {
   #   error "-incdir not yet supported"
   #}
   switch $format {
      "vhdl" {
         foreach f $files {
            set_global_assignment -name VHDL_FILE $f -library $library
         }
      }
      "verilog" {
         foreach d $define {
            set_global_assignment -name VERILOG_MACRO $d
         }
         foreach f $files {
            set_global_assignment -name VERILOG_FILE $f -library $library
         }
      }
   }
}

if { [catch { puts "Quartus hdl_common script" } ] } {
    # Disable puts for Quartus (doesn't work with the GUI since no stdout channel)
    proc hdl_puts { msg } {
    }
}
