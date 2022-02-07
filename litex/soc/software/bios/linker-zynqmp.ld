/*******************************************************************/
/* Copyright (c) 2010-2016 Xilinx, Inc.  All rights reserved.      */
/*                                                                 */
/* Description : Cortex-A53 Linker Script                          */
/*******************************************************************/

INCLUDE generated/output_format.ld
ENTRY(_start)

INCLUDE generated/regions.ld

_STACK_SIZE = DEFINED(_STACK_SIZE) ? _STACK_SIZE : 0x2000;
_HEAP_SIZE = DEFINED(_HEAP_SIZE) ? _HEAP_SIZE : 0x2000;

_EL0_STACK_SIZE = DEFINED(_EL0_STACK_SIZE) ? _EL0_STACK_SIZE : 1024;
_EL1_STACK_SIZE = DEFINED(_EL1_STACK_SIZE) ? _EL1_STACK_SIZE : 2048;
_EL2_STACK_SIZE = DEFINED(_EL2_STACK_SIZE) ? _EL2_STACK_SIZE : 1024;

ENTRY(_vector_table)

SECTIONS
{
.text : {
   _ftext = .;
   KEEP (*(.vectors))
   *(.boot)
   *(.text)
   *(.text.*)
   *(.gnu.linkonce.t.*)
   *(.plt)
   *(.gnu_warning)
   *(.gcc_execpt_table)
   *(.glue_7)
   *(.glue_7t)
   *(.ARM.extab)
   *(.gnu.linkonce.armextab.*)
} > sram

.commands :
{
    PROVIDE_HIDDEN (__bios_cmd_start = .);
    KEEP(*(.bios_cmd))
    PROVIDE_HIDDEN (__bios_cmd_end = .);
} > sram

.init (ALIGN(64)) : {
   PROVIDE_HIDDEN (__bios_init_start = .);
   KEEP (*(.bios_init))
   PROVIDE_HIDDEN (__bios_init_end = .);
} > sram

.fini (ALIGN(64)) : {
   KEEP (*(.fini))
} > sram

.interp : {
   KEEP (*(.interp))
} > sram

.note-ABI-tag : {
   KEEP (*(.note-ABI-tag))
} > sram

.rodata : {
   . = ALIGN(64);
   __rodata_start = .;
   *(.rodata)
   *(.rodata.*)
   *(.gnu.linkonce.r.*)
   __rodata_end = .;
} > sram

.rodata1 : {
   . = ALIGN(64);
   __rodata1_start = .;
   *(.rodata1)
   *(.rodata1.*)

    /* Make sure the file is aligned on disk as well
       as in memory; CRC calculation requires that. */
    FILL(0);
    . = ALIGN(8);

   __rodata1_end = .;
} > sram

.sdata2 : {
   . = ALIGN(64);
   __sdata2_start = .;
   *(.sdata2)
   *(.sdata2.*)
   *(.gnu.linkonce.s2.*)
   __sdata2_end = .;
} > sram

.sbss2 : {
   . = ALIGN(64);
   __sbss2_start = .;
   *(.sbss2)
   *(.sbss2.*)
   *(.gnu.linkonce.sb2.*)
   __sbss2_end = .;
} > sram

.data : {
   . = ALIGN(64);
   __data_start = .;
   *(.data)
   *(.data.*)
   *(.gnu.linkonce.d.*)
   *(.jcr)
   *(.got)
   *(.got.plt)
   __data_end = .;
} > sram

.data1 : {
   . = ALIGN(64);
   __data1_start = .;
   *(.data1)
   *(.data1.*)

    /* Make sure the file is aligned on disk as well
       as in memory; CRC calculation requires that. */
    FILL(0);
    . = ALIGN(8);

   __data1_end = .;
} > sram

.got : {
   *(.got)
} > sram

.got1 : {
   *(.got1)
} > sram

.got2 : {
   *(.got2)
} > sram

.note.gnu.build-id : {
   KEEP (*(.note.gnu.build-id))
} > sram

.ctors : {
   . = ALIGN(64);
   __CTOR_LIST__ = .;
   ___CTORS_LIST___ = .;
   KEEP (*crtbegin.o(.ctors))
   KEEP (*(EXCLUDE_FILE(*crtend.o) .ctors))
   KEEP (*(SORT(.ctors.*)))
   KEEP (*(.ctors))
   __CTOR_END__ = .;
   ___CTORS_END___ = .;
} > sram

.dtors : {
   . = ALIGN(64);
   __DTOR_LIST__ = .;
   ___DTORS_LIST___ = .;
   KEEP (*crtbegin.o(.dtors))
   KEEP (*(EXCLUDE_FILE(*crtend.o) .dtors))
   KEEP (*(SORT(.dtors.*)))
   KEEP (*(.dtors))
   __DTOR_END__ = .;
   ___DTORS_END___ = .;
} > sram

.fixup : {
   __fixup_start = .;
   *(.fixup)
   __fixup_end = .;
} > sram

.eh_frame : {
   *(.eh_frame)
} > sram

.eh_framehdr : {
   __eh_framehdr_start = .;
   *(.eh_framehdr)
   __eh_framehdr_end = .;
} > sram

.gcc_except_table : {
   *(.gcc_except_table)
} > sram

.mmu_tbl0 (ALIGN(4096)) : {
   __mmu_tbl0_start = .;
   *(.mmu_tbl0)
   __mmu_tbl0_end = .;
} > sram

.mmu_tbl1 (ALIGN(4096)) : {
   __mmu_tbl1_start = .;
   *(.mmu_tbl1)
   __mmu_tbl1_end = .;
} > sram

.mmu_tbl2 (ALIGN(4096)) : {
   __mmu_tbl2_start = .;
   *(.mmu_tbl2)
   __mmu_tbl2_end = .;
} > sram

.ARM.exidx : {
   __exidx_start = .;
   *(.ARM.exidx*)
   *(.gnu.linkonce.armexidix.*.*)
   __exidx_end = .;
} > sram

.preinit_array : {
   . = ALIGN(64);
   __preinit_array_start = .;
   KEEP (*(SORT(.preinit_array.*)))
   KEEP (*(.preinit_array))
   __preinit_array_end = .;
} > sram

.init_array : {
   . = ALIGN(64);
   __init_array_start = .;
   KEEP (*(SORT(.init_array.*)))
   KEEP (*(.init_array))
   __init_array_end = .;
} > sram

.fini_array : {
   . = ALIGN(64);
   __fini_array_start = .;
   KEEP (*(SORT(.fini_array.*)))
   KEEP (*(.fini_array))
   __fini_array_end = .;
} > sram

.ARM.attributes : {
   __ARM.attributes_start = .;
   *(.ARM.attributes)
   __ARM.attributes_end = .;
} > sram

.sdata : {
   . = ALIGN(64);
   __sdata_start = .;
   *(.sdata)
   *(.sdata.*)
   *(.gnu.linkonce.s.*)
   __sdata_end = .;
} > sram

.sbss (NOLOAD) : {
   . = ALIGN(64);
   __sbss_start = .;
   *(.sbss)
   *(.sbss.*)
   *(.gnu.linkonce.sb.*)
   . = ALIGN(64);
   __sbss_end = .;
} > sram

.tdata : {
   . = ALIGN(64);
   __tdata_start = .;
   *(.tdata)
   *(.tdata.*)
   *(.gnu.linkonce.td.*)
   __tdata_end = .;
} > sram

.tbss : {
   . = ALIGN(64);
   __tbss_start = .;
   *(.tbss)
   *(.tbss.*)
   *(.gnu.linkonce.tb.*)
   __tbss_end = .;
} > sram

.bss (NOLOAD) : {
   . = ALIGN(64);
   __bss_start__ = .;
   *(.bss)
   *(.bss.*)
   *(.gnu.linkonce.b.*)
   *(COMMON)
   . = ALIGN(64);
   __bss_end__ = .;
} > sram

_SDA_BASE_ = __sdata_start + ((__sbss_end - __sdata_start) / 2 );

_SDA2_BASE_ = __sdata2_start + ((__sbss2_end - __sdata2_start) / 2 );

.stack (NOLOAD) : {
   . = ALIGN(64);
   _el3_stack_end = .;
   . += _STACK_SIZE;
   __el3_stack = .;
   _el2_stack_end = .;
   . += _EL2_STACK_SIZE;
   . = ALIGN(64);
   __el2_stack = .;
   _el1_stack_end = .;
   . += _EL1_STACK_SIZE;
   . = ALIGN(64);
   __el1_stack = .;
   _el0_stack_end = .;
   . += _EL0_STACK_SIZE;
   . = ALIGN(64);
   __el0_stack = .;
} > sram

_end = .;
}

PROVIDE(_edata_rom = LOADADDR(.data) + SIZEOF(.data));
