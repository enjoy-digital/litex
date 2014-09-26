set HDL_TOOLTYPE SYNTHESIS
set HDL_TOOLNAME XST
set HDL_PUTS puts
set HDL_MSG_FORMAT "********** %s **********"

proc hdl_tool_library {lib_list} {
}

proc hdl_tool_compile {format version incdirs library define files behavioral} {
   global PROJECT_FILE

   # do not use append, based on http://wiki.tcl.tk/1241
   set projectfile [open $PROJECT_FILE {WRONLY CREAT APPEND}]

   if {[llength $define]} {
      error "-define not yet supported"
   }
   if {[llength $incdirs]} {
      error "-incdirs not yet supported"
   }
   puts "checking format"
   switch $format {
      "vhdl" {
         foreach f $files {
            puts $projectfile "vhdl $library $f"
         }
      }
      "verilog" {
        foreach f $files {
            puts $projectfile "verilog $library $f"
         }
      }
   }

   close $projectfile

}