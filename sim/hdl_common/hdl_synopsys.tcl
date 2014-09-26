set HDL_TOOLTYPE SYNTHESIS
set HDL_TOOLNAME synopsys
set HDL_PUTS puts
set HDL_MSG_FORMAT "\n********** %s **********\n"

proc hdl_tool_library {lib_list} {
   foreach l $lib_list {
      set path [get_lib_path]/$l
      sh touch $path
      sh rm -r $path
      sh mkdir $path
      define_design_lib $l -path $path
   }
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
         puts "Compiling source file $f"
      }
      analyze -format $format -work $library $f
      puts ""
   }
   # Remove include paths
   set search_path [lrange $search_path [llength $incdirs] end]
}
