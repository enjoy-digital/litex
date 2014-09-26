##############################################################################
# Define some global variables
##############################################################################

if {![info exists HDL_LIBRARIES]} {
   set HDL_LIBRARIES ()
}
set HDL_TARGET "default_target"
set HDL_PATH [pwd]
set HDL_WORK "work"

# Uncomment the following line to generate a log file for debug
#set HDL_LOG [open "hdl_common.log" "w"]

##############################################################################
# Some utilities
##############################################################################

# Extract first element from a list (for argument processing)
proc extract_first {list_name {option ""}} {
   upvar $list_name mylist
   if {[string length $option]>0 && [llength $mylist]==0} {
      error "Missing argument for option $option"
   }
   set first  [lindex $mylist 0]
   if {[string length $option]>0 && [string match "-*" $first]} {
      error "Missing argument for option $option"
   }
   set mylist [lrange $mylist 1 end]
   return $first
}

# Clean-up file path
proc clean_path {f} {
   # Add trailing /
   set f "$f/"
   # Remove double / (excepted leading)
   while {[regsub {(.)//} $f "\1/" f]} {}
   # Remove .
   while {[regsub {/\./} $f "/" f]} {}
   # Remove ..
   while {[regsub {/[^/.]+/\.\./} $f "/" f]} {}
   # Remove trailing /
   regsub {/$} $f "" f
   return $f
}

# Translate relative paths to absolute paths
proc get_full_path {files} {
   global HDL_PATH
   set r {}
   # For DOS paths, replace \ by /
   regsub -all {\\} $files "/" files
   foreach f $files {
      hdl_debug "  $f"
      # Append file path
      if {[string match "/*" $f] || [string match "?:/*" $f]} {
         # Path is an absolute path
         hdl_warning "Using absolute path $f"
      } else {
         # Path is a relative path
         set f [clean_path $HDL_PATH/$f]
      }
      hdl_debug "    => $f"
      lappend r $f
      # Check access to file
      if {![file readable $f]} {
         error "Cannot read file $f"
      }
   }
   return $r
}

# Check if value match any pattern in the list
proc match_list {mlist value} {
   set match 0
   foreach m $mlist {
      if [string match $m $value] {
         set match 1
      }
   }
   return $match
}

proc get_lib_path {} {
   if [file isdirectory "/cad/trash"] {
      set libs "/cad/trash[pwd]/libs"
   } elseif [file isdirectory "e:/trash"] {
      set libs [pwd]
      # Replace D:/ by D/ for local drive
      regsub ":" $libs "" libs
      # Remove leading // for network drive
      regsub "//" $libs "" libs
      set libs "e:/trash/$libs"
   } else {
      # No "trash" directory on this machine => work locally
      set libs "./libs"
   }
   file mkdir $libs
   return $libs
}

##############################################################################
# Procedures to display messages
##############################################################################

# Write message to log file if logging enabled
proc hdl_log { msg } {
   global HDL_LOG
   if [info exists HDL_LOG] {
      puts $HDL_LOG $msg
      flush $HDL_LOG
   }
   return
}

# Debug messages are sent only to log file
proc hdl_debug { msg } {
   hdl_log "hdl_common - Debug:   $msg"
   return
}

# According to the tool, "puts" or "echo" should be used
# HDL_PUTS variable is used for this purpose
# All message are also sent to log file
proc hdl_puts { msg } {
   global HDL_PUTS
   $HDL_PUTS $msg
   hdl_log $msg
   return
}

proc hdl_note { msg } {
   hdl_puts "hdl_common - Note:    $msg"
   return
}

proc hdl_warning { msg } {
   hdl_puts "hdl_common - Warning: $msg"
   return
}

proc hdl_message { args } {
   global HDL_MSG_FORMAT
   hdl_puts [format $HDL_MSG_FORMAT [join $args " "]]
   return
}

##############################################################################
# Procedures for compilation scripts
##############################################################################

# Compile source files
proc hdl_compile { args } {
   global HDL_TOOLTYPE HDL_TOOLNAME HDL_TARGET HDL_LIBRARIES HDL_WORK
   # Default values
   set format  ""
   set version "93"
   set files   {}
   set incdirs {}
   set only_for {}
   set not_for {}
   set toolname {}
   set tooltype "*"
   set library $HDL_WORK
   set define {}
   set behavioral 0

   # Decode arguments
   while {[llength $args]} {
      set arg [extract_first args]
      switch -glob -- $arg {
         "-f" {
            set format [extract_first args "-f"]
         }
         "-v" {
            set version [extract_first args "-version"]
         }
         "-only_for" {
            set only_for [concat $only_for [extract_first args "-only_for"]]
         }
         "-not_for" {
            set not_for [concat $not_for [extract_first args "-not_for"]]
         }
         "-sim" {
            set tooltype "SIMULATION"
            set behavioral 1
         }
         "-syn" {
            set tooltype "SYNTHESIS"
            set behavioral 0
         }
         "-tool" {
            set toolname [concat $toolname [extract_first args "-tool"]]
         }
         "-incdir" {
            set incdirs [concat $incdirs [extract_first args "-incdir"]]
         }
         "-lib" {
            set library [extract_first args "-lib"]
            if {[string match "work" $library]} {
               hdl_warning "Specifying '-lib work' is useless"
            }
         }
         "-define" {
            set define [concat $define [extract_first args "-define"]]
         }
         "-*" {
            error "Unsupported argument $arg"
         }
         default {
            set files [concat $files $arg]
         }
      }
   }

   # Check arguments
   if {![llength $files]} {
      error "No file to compile"
   }
   # If no "-only_for" option given, use file for any target
   if {[llength $only_for]==0} {
      set only_for {*}
   }
   # If no "-tool" option given, use file for any tool
   if {[llength $toolname]==0} {
      set toolname {*}
   }

   # Check if compilation is required
   if {[match_list $only_for $HDL_TARGET] && ![match_list $not_for $HDL_TARGET] &&
       [string match $tooltype $HDL_TOOLTYPE] && [match_list $toolname $HDL_TOOLNAME]} {
      # Create library if needed
      if {[lsearch -exact $HDL_LIBRARIES $library]<0} {
         hdl_note "Creating library $library"
         lappend HDL_LIBRARIES $library
         hdl_tool_library $library
      }
      # Compile files
      foreach f $files {
         # Warning if dummy file is used
         if {[string match "*dummy*" [string tolower $f]]} {
            hdl_note "Using [file tail $f]"
         }
         # Determine format
         if {![llength $format]} {
            if {[string match "*.vh?*" $f]} {
               set format "vhdl"
            } elseif {[string match "*.v*" $f]} {
               set format "verilog"
               set version "sv"
            } elseif {[string match "*.sv" $f]} {
               set format "verilog"
               set version "sv"
            }
         }
      }
      hdl_tool_compile $format $version [get_full_path $incdirs] $library $define [get_full_path $files] $behavioral
   }
   return
}

# Change directory
proc hdl_cd { path } {
   global HDL_PATH
   set HDL_PATH [get_full_path $path]
   hdl_debug "New path is $HDL_PATH"
   return
}

# Execute script
proc hdl_source { args } {
   global HDL_PATH HDL_TARGET HDL_WORK HDL_TOOLTYPE HDL_TOOLNAME
   # Save original values
   set save_path   $HDL_PATH
   set save_target $HDL_TARGET
   set save_work   $HDL_WORK
   # Default value
   set files {}
   set toolname {}
   set tooltype "*"
   set only_for {}
   set not_for {}
   # Process options
   while {[llength $args]} {
      set arg [extract_first args]
      switch -glob -- $arg {
         "-lib" {
            set HDL_WORK [extract_first args "-lib"]
            if {[string match "work" $HDL_WORK]} {
               hdl_warning "Specifying '-lib work' is useless"
            }
         }
         "-target" {
            set HDL_TARGET [extract_first args "-target"]
         }
         "-sim" {
            set tooltype "SIMULATION"
            set behavioral 1
         }
         "-syn" {
            set tooltype "SYNTHESIS"
            set behavioral 0
         }
         "-tool" {
            set toolname [concat $toolname [extract_first args "-tool"]]
         }
         "-only_for" {
            set only_for [concat $only_for [extract_first args "-only_for"]]
         }
         "-not_for" {
            set not_for [concat $not_for [extract_first args "-not_for"]]
         }
         "-*" {
            error "Unsupported argument $arg"
         }
         default {
            set files [concat $files $arg]
         }
      }
   }
   # Check arguments
   if {![llength $files]} {
      error "No script specified"
   }
   # If no "-only_for" option given, use file for any target
   if {[llength $only_for]==0} {
      set only_for {*}
   }
   # If no "-tool" option given, use file for any tool
   if {[llength $toolname]==0} {
      set toolname {*}
   }

   # Check if compilation is required
   if {[match_list $only_for $HDL_TARGET] && ![match_list $not_for $HDL_TARGET] &&
       [string match $tooltype $HDL_TOOLTYPE] && [match_list $toolname $HDL_TOOLNAME]} {
      # Source scripts
      foreach script $files {
         # Change directory to script location
         hdl_cd [file dirname $script]
         # Execute script
         set script [get_full_path [file tail $script]]
         hdl_note "Source $script ($HDL_TARGET)"
         uplevel source $script
         # Restore original path
         set HDL_PATH $save_path
         hdl_debug "Back to directory $HDL_PATH"
      }
   }
   # Restore original values
   set HDL_TARGET $save_target
   set HDL_WORK   $save_work
   #puts "Back to $HDL_PATH"
   return
}

# Specify target
proc hdl_set_target { args } {
   global HDL_TARGET env
   # Default values
   set use_env 0
   set default ""
   set target ""
   # Decode arguments
   while {[llength $args]} {
      set arg [extract_first args]
      switch -glob -- $arg {
         "-env" {
            set use_env 1
         }
         "-default" {
            set default [extract_first args "-default"]
         }
         "-*" {
            error "Unsupported argument $arg"
         }
         default {
            set target $arg
         }
      }
   }
   # Check arguments
   if {[llength $target]} {
      set HDL_TARGET $target
      hdl_note "Using target $HDL_TARGET"
   } elseif {$use_env} {
      if {[info exists env(HDL_TARGET)]} {
         set HDL_TARGET $env(HDL_TARGET)
         hdl_note "Using target $HDL_TARGET (from environment variable HDL_TARGET)"
      } elseif {[llength $default]} {
         set HDL_TARGET $default
         hdl_note "Using default target $HDL_TARGET (environment variable HDL_TARGET not defined)"
      } else {
         error "No environment variable defined and no default target"
      }
   } else {
      error "Missing argument"
   }
   return
}

##############################################################################

# clock is an invalid command name for Synplify at least until version 2010.09
# hdl_debug [clock format [clock seconds]]
