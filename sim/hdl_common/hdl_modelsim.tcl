# Set the option CHECK_SYNTHESIS to 1 if you want to have -check_synthesis in simulation. For now
# tools like Modelsim generate too many false positives so it is disabled by default:

set CHECK_SYNTHESIS 0

set NO_DEBUG 0

set HDL_TOOLTYPE SIMULATION
set HDL_TOOLNAME modelsim
set HDL_PUTS echo
set HDL_MSG_FORMAT "********** %s **********"

# Return the directory containing library lib
proc getvmap {lib} {
   if {[catch {vmap $lib} result]} {
      # Library does not exist yet => default directory
      return $lib
   }
   set dir  ""
   # Get directory returned by vmap
   regexp { maps to directory (.*)\.$} $result match dir
   return $dir
}

proc hdl_tool_library {lib} {
   set lib [string tolower $lib]
   # Delete library
   set path [getvmap $lib]
   if {[file isdirectory $path]} {
	   catch {
	      vdel -lib $path -all
	   }
	}
   # Create library
   set path [get_lib_path]/$lib
   vlib $path
   vmap $lib $path
}

proc hdl_tool_compile {format version incdirs library define files behavioral} {
   global CHECK_SYNTHESIS
   global NO_DEBUG
   switch $format {
      "vhdl" {
         set command vcom
         if { $version == 87 } {
            lappend command -87
         } elseif { $version == 93 } {
            lappend command -93
         }
         # More strict for synthesizable modules
         if { ! $behavioral && $CHECK_SYNTHESIS } {
            lappend command -check_synthesis
         }
      }
      "verilog" {
         set command vlog
         if {$version == "sv"} {
            lappend command -sv
         }
         lappend command -timescale "1ns/1ns"
         foreach d $define {
            lappend command +define+$d
         }
         foreach i $incdirs {
            lappend command +incdir+$i
         }
      }
   }
   if {$NO_DEBUG} {
      lappend command -nodebug
   }
   lappend command -work [string tolower $library]
   lappend command -quiet
   foreach f $files {
      lappend command $f
   }
   puts -nonewline [eval $command]
   return
}
