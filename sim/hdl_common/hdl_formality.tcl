set HDL_TOOLTYPE SYNTHESIS
set HDL_TOOLNAME formality
set HDL_PUTS puts
set HDL_MSG_FORMAT "\n********** %s **********\n"

proc hdl_tool_library {lib} {
   define_design_lib $lib -path lib_$lib
}

proc hdl_tool_compile {format version incdirs library define files behavioral} {
   global search_path
   if {[llength $define]} {
      error "-define not yet supported"
   }
   # Add include paths
   set search_path [concat $incdirs $search_path]
   # Compile files
   foreach f $files {
      if {[string match $format "vhdl"]} {
         if {[string match $version "93"]} {
           read_vhdl -93 -libname $library $f
         } else {
           read_vhdl -libname $library $f
         }
      } else {
         read_verilog -01 -libname $library $f
      }
      puts ""
   }
   # Remove include paths
   set search_path [lrange $search_path [llength $incdirs] end]
}
