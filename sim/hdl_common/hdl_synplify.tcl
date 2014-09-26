set HDL_TOOLTYPE SYNTHESIS
set HDL_TOOLNAME synplify
set HDL_PUTS puts
set HDL_MSG_FORMAT "********** %s **********"

proc hdl_tool_library {lib_list} {
}

proc hdl_tool_compile {format version incdirs library define files behavioral} {
   if {[llength $define]} {
      error "-define not yet supported"
   }
   switch $format {
      "vhdl" {
         foreach f $files {
            add_file -vhdl -lib $library $f
         }
      }
      "verilog" {
         foreach i $incdirs {
            set_option -include_path "$i"
         }
         foreach f $files {
            add_file -verilog $f
         }
      }   
      "ngc" {
         foreach i $incdirs {
            set_option -include_path "$i"
         }
         foreach f $files {
            add_file -xilinx $f
         }         
      }
   }
}
