# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("uptime", [False, True])
def test_nested_deadlines_and_counter_wrap(tmp_path, uptime):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "csr.h").write_text("")
    (generated / "soc.h").write_text("#define CONFIG_CLOCK_FREQUENCY 1000000\n")
    source = tmp_path / "timeout.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
static uint64_t cycles;
static uint32_t enabled, reload;
static unsigned int loads;
static uint32_t timer0_en_read(void) { return enabled; }
static uint32_t timer0_reload_read(void) { return reload; }
static void timer0_en_write(uint32_t v) { enabled = v; }
static void timer0_reload_write(uint32_t v) { reload = v; }
static void timer0_load_write(uint32_t v) { (void)v; loads++; }
static void timer0_update_value_write(uint32_t v) { (void)v; }
static uint32_t timer0_value_read(void) { return UINT32_MAX - (uint32_t)cycles; }
static void timer0_uptime_latch_write(uint32_t v) { (void)v; }
static uint64_t timer0_uptime_cycles_read(void) { return cycles; }
#include <libbase/timeout.c>

int main(void)
{
    struct timeout outer, inner;
    cycles = UINT64_MAX - 5;
    timeout_start(&outer, 10);
    assert(!timeout_expired(&outer));
    cycles += 4;
    timeout_start(&inner, 3);
    assert(!timeout_expired(&outer));
    cycles += 2;
    assert(!timeout_expired(&inner));
    assert(!timeout_expired(&outer));
    cycles++;
    assert(timeout_expired(&inner));
    assert(!timeout_expired(&outer));
    cycles += 3;
    assert(timeout_expired(&outer));
    assert(timeout_expired(&outer));
#ifndef CSR_TIMER0_UPTIME_CYCLES_ADDR
    assert(loads == 1);
#endif
    timeout_start(&inner, 0);
    assert(timeout_expired(&inner));
    return 0;
}
''')
    binary = tmp_path / "timeout"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software",
        *(["-DCSR_TIMER0_UPTIME_CYCLES_ADDR=1"] if uptime else []),
        str(source), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])
