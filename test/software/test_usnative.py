#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

"""Host C tests for native profile selection and bounded firmware CSR polling."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "litex/soc/software/liblitedram/usnative"
BIOS_INCLUDE = ROOT / "litex/soc/software/bios"
CC = shutil.which(os.environ.get("CC", "gcc"))

@unittest.skipUnless(CC, "Host C compiler required")
class TestUSNativeFirmware(unittest.TestCase):
    def compile_run(self, code, success=True, extra_flags=()):
        with tempfile.TemporaryDirectory(prefix="usnative_bios_") as temporary:
            directory = Path(temporary)
            source = directory / "test.c"
            binary = directory / ("test.exe" if os.name == "nt" else "test")
            source.write_text(code)
            result = subprocess.run([CC, "-std=c99", "-Werror=implicit-function-declaration", *extra_flags,
                "-I", str(INCLUDE), "-I", str(BIOS_INCLUDE), str(source), "-o", str(binary)],
                capture_output=True, text=True, timeout=60)
            if not success:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("#error", result.stderr)
                return
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def profile(self, rate=2400, extra="", check=""):
        clock, cl, cwl, rd, wr = {2400: (300000000,17,12,2,3), 2667: (333333333,19,14,0,1),
            2933: (366666666,21,16,2,3), 3200: (400000000,24,16,3,3)}[rate]
        operating_rd = 2 if rate == 3200 else rd
        return f'''
#define SDRAM_PHY_DDR4
#define SDRAM_PHY_DATABITS 16
#define SDRAM_PHY_DFI_DATABITS 32
#define SDRAM_PHY_PHASES 4
#define SDRAM_PHY_XDR 2
#define SDRAM_PHY_DELAYS 512
#define SDRAM_PHY_BITSLIPS 8
#define SDRAM_PHY_CMD_LATENCY 5
#define MAIN_RAM_BASE 0x40000000
#define MAIN_RAM_SIZE 0x01200000
#define CSR_DDRPHY_RIU_BUSY_ADDR 1
#define CSR_DDRPHY_RIU_VALID_ADDR 1
#define CSR_DDRPHY_TAP_STATUS_VALID_ADDR 1
#define CONFIG_CLOCK_FREQUENCY {clock}
#define SDRAM_PHY_CL {cl}
#define SDRAM_PHY_CWL {cwl}
#define SDRAM_PHY_RDPHASE {rd}
#define SDRAM_PHY_WRPHASE {wr}
{extra}
#include "profile.h"
static int selected=-1;
static void command_p0(unsigned value) {{ (void)value; selected=0; }}
static void command_p1(unsigned value) {{ (void)value; selected=1; }}
static void command_p2(unsigned value) {{ (void)value; selected=2; }}
static void command_p3(unsigned value) {{ (void)value; selected=3; }}
int main(void) {{
 USNATIVE_RD_COMMAND(1); if(selected!={operating_rd}) return 1;
 if(USNATIVE_RDPHASE!={operating_rd}) return 2;
 if(USNATIVE_BOOT_TX_DELAY!={72 if rate == 3200 else 88}) return 3;
 if(USNATIVE_BOOT_RX_DELAY!={48 if rate == 3200 else 32}) return 4;
 USNATIVE_WR_COMMAND(1);
 {check}
 return selected!={wr};
}}
'''

    def test_default_profiles_without_dma_or_debug_csrs(self):
        for rate in (2400, 2667):
            with self.subTest(rate=rate):
                self.compile_run(self.profile(rate, check="USNATIVE_DEBUG(unknown_debug_function()); USNATIVE_SNAPSHOT();"))

    def test_high_rates_require_overclock_opt_in(self):
        for rate in (2933, 3200):
            with self.subTest(rate=rate):
                self.compile_run(self.profile(rate), False)
                self.compile_run(self.profile(rate, extra="#define CONFIG_SDRAM_USNATIVE_OVERCLOCK"))

    def test_3200_operating_phase_is_independent_of_debug(self):
        for debug in (False, True):
            with self.subTest(debug=debug):
                extra = "#define CONFIG_SDRAM_USNATIVE_OVERCLOCK\n"
                if debug:
                    extra += "#define CONFIG_SDRAM_USNATIVE_DEBUG\n"
                self.compile_run(self.profile(3200, extra=extra))

    def test_reject_wrong_phase(self):
        self.compile_run(self.profile(extra="#undef SDRAM_PHY_RDPHASE\n#define SDRAM_PHY_RDPHASE 1"), False)

    def test_reject_wrong_data_width(self):
        self.compile_run(self.profile(extra="#undef SDRAM_PHY_DATABITS\n#define SDRAM_PHY_DATABITS 32"), False)

    def test_dma_opt_in_requires_engine(self):
        self.compile_run(self.profile(extra="#define CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION"), False)

    def test_dma_opt_in_profile_is_independent_of_debug(self):
        dma = r'''
#undef MAIN_RAM_SIZE
#define MAIN_RAM_SIZE 0x08000000
#define CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
#define CONFIG_SDRAM_NATIVE_DMA_TEST
#define CONFIG_SDRAM_NATIVE_DMA_BANK_GROUP_INTERLEAVING
#define CSR_DMA_BENCH_START_ADDR 1
#define CSR_DMA_BENCH_DQ_ERROR_MASK_ADDR 1
#define CSR_DMA_BENCH_DATA_WIDTH_ADDR 1
'''
        self.compile_run(self.profile(extra=dma,
            check='USNATIVE_DEBUG("debug disabled\\n");'))
        self.compile_run(self.profile(extra="#include <stdio.h>\n#define CONFIG_SDRAM_USNATIVE_DEBUG\n" + dma,
            check='USNATIVE_DEBUG("debug enabled\\n");'))
        self.compile_run(self.profile(extra=dma.replace(
            "#define CONFIG_SDRAM_NATIVE_DMA_BANK_GROUP_INTERLEAVING\n", "")))

    def test_dma_refinement_compiles_with_debug_on_and_off(self):
        source = r'''
#include <stdint.h>
#include <stdio.h>
#define __USNATIVE_DMA_IO_H
static unsigned nd_program(unsigned *centers, unsigned lanes, int offset)
    {(void)centers;(void)lanes;(void)offset;return 1;}
static unsigned nb_fail(unsigned error) {return error;}
static unsigned nd_dma_check(unsigned random, unsigned readonly)
    {(void)random;(void)readonly;return 0;}
static uint32_t dma_bench_dq_error_mask_read(void) {return 0;}
static void ddrphy_training_stage_write(unsigned stage) {(void)stage;}
#define USNATIVE_SNAPSHOT() do {} while (0)
#ifdef TEST_DEBUG
#define USNATIVE_DEBUG(...) printf(__VA_ARGS__)
#else
#define USNATIVE_DEBUG(...) do {} while (0)
#endif
#include "native_dma_calibration.h"
int main(void) {unsigned centers[16]={0};return nd_dma_refine(centers);}
'''
        flags = ("-Wall", "-Wformat=2", "-Werror=format",
                 "-Werror=unused-variable", "-Werror=unused-but-set-variable")
        self.compile_run(source, extra_flags=flags)
        self.compile_run("#define TEST_DEBUG\n#define CONFIG_SDRAM_USNATIVE_DEBUG\n" + source,
            extra_flags=flags)

    def test_dma_benchmark_reports_selected_hardware_mode(self):
        self.compile_run(r'''
#include <string.h>
#include "native_dma_mode.h"
int main(void) {
 return NATIVE_DMA_BANK_GROUP_INTERLEAVED != 0 ||
     strcmp(NATIVE_DMA_MODE_NAME, "standard-native-port");
}
''')

    def test_dma_completion_deadline_tracks_hardware_cycles(self):
        for frequency, expected_us in ((125_000_000, 17_000_000),
                                       (250_000_000, 9_000_000),
                                       (400_000_000, 6_000_000)):
            self.compile_run(f'''
#define CONFIG_CLOCK_FREQUENCY {frequency}u
#include "native_dma_timeout.h"
int main(void) {{ return native_dma_completion_timeout_us() != {expected_us}u; }}
''')

    def test_dma_admission_for_native_and_component_phys(self):
        self.compile_run(r'''
#include <assert.h>
#define CONFIG_SDRAM_USNATIVE_XEM8320
static unsigned ready, stage, error, bist_only;
static unsigned ddrphy_ready_read(void) { return ready; }
static unsigned ddrphy_training_stage_read(void) { return stage; }
static unsigned ddrphy_training_error_read(void) { return error; }
static unsigned ddrphy_bisc_only_read(void) { return bist_only; }
#include "native_dma_admission.h"
int main(void) {
 assert(!native_dma_admission_ready());
 ready=1; stage=5; assert(native_dma_admission_ready());
 error=1; assert(!native_dma_admission_ready());
 error=0; bist_only=1; assert(!native_dma_admission_ready());
 return 0;
}
''')
        self.compile_run(r'''
#include <assert.h>
#define CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
static unsigned admitted;
static unsigned dma_bench_software_ready_read(void) { return admitted; }
#include "native_dma_admission.h"
int main(void) {
 assert(!native_dma_admission_ready());
 admitted=1; assert(native_dma_admission_ready());
 return 0;
}
''')
        self.compile_run(r'''
#include "native_dma_admission.h"
int main(void) { return native_dma_admission_ready(); }
''', False)
        self.compile_run(r'''
#include <string.h>
#define CONFIG_SDRAM_NATIVE_DMA_BANK_GROUP_INTERLEAVING
#include "native_dma_mode.h"
int main(void) {
 return NATIVE_DMA_BANK_GROUP_INTERLEAVED != 1 ||
     strcmp(NATIVE_DMA_MODE_NAME, "paired-bank-group-interleaved");
}
''')

    def test_reject_insufficient_scratch_ram(self):
        self.compile_run(self.profile(extra="#undef MAIN_RAM_SIZE\n#define MAIN_RAM_SIZE 0x01000000"), False)

    def test_dma_completion_timeout_and_integrity(self):
        self.compile_run(r'''
#include <assert.h>
#define USNATIVE_DMA_POLL_LIMIT 8
static unsigned done_after, polls, busy, fault, errors, starts, readonly;
static void flush_cpu_dcache(void) {} static void flush_l2_cache(void) {}
static void cdelay(unsigned value) {(void)value;}
static unsigned dma_bench_busy_read(void) {return busy;}
static unsigned dma_bench_fault_read(void) {return fault;}
static void dma_bench_base_write(unsigned value) {assert(value==0x01000000);}
static void dma_bench_length_write(unsigned value) {assert(value==0x04000000);}
static void dma_bench_random_write(unsigned value) {(void)value;}
static void dma_bench_read_only_write(unsigned value) {readonly=value;}
static void dma_bench_timeout_write(unsigned value) {assert(value>0);}
static void dma_bench_start_write(unsigned value) {assert(value==1);++starts;}
static unsigned dma_bench_done_read(void) {return ++polls>=done_after;}
static unsigned dma_bench_read_beats_read(void) {return 0x200000;}
static unsigned dma_bench_write_beats_read(void) {return readonly?0:0x200000;}
static unsigned dma_bench_errors_read(void) {return errors;}
#include "native_dma_io.h"
int main(void) {
 done_after=3; assert(nd_dma_check(0,0)==0 && polls==3 && starts==1);
 polls=0; done_after=99; assert(nd_dma_check(0,0)==0xffffffffu && polls==8);
 polls=0; done_after=1; errors=17; assert(nd_dma_check(1,1)==17 && readonly==1);
 busy=1; unsigned old=starts; assert(nd_dma_check(0,0)==0xffffffffu && starts==old);
 busy=0; fault=3; assert(nd_dma_check(0,0)==0xffffffffu && starts==old);
 return 0;
}
''')

    def test_riu_timeout_stale_response_and_tap_freshness(self):
        self.compile_run(r'''
#include <assert.h>
static unsigned busy, error, valid=1, starts, polls, tap_valid=1;
static void cdelay(unsigned value) {(void)value;}
static unsigned ddrphy_riu_busy_read(void) {++polls;return busy;}
static unsigned ddrphy_riu_error_read(void) {return error;}
static unsigned ddrphy_riu_valid_read(void) {return valid;}
static unsigned ddrphy_riu_rdata_read(void) {return 0x1234;}
static void ddrphy_riu_nibble_write(unsigned v) {(void)v;}
static void ddrphy_riu_address_write(unsigned v) {(void)v;}
static void ddrphy_riu_wdata_write(unsigned v) {(void)v;}
static void ddrphy_riu_write_write(unsigned v) {(void)v;++starts;}
static void ddrphy_riu_read_write(unsigned v) {(void)v;++starts;}
static unsigned ddrphy_tap_status_valid_read(void) {return tap_valid;}
#include "native_status_io.h"
int main(void) {
 unsigned result=0;
 assert(native_riu_access(1,3,0,0,&result) && result==0x1234);
 busy=1; polls=0; unsigned old=starts;
 assert(!native_riu_access(1,3,0,0,&result) && polls==10000 && starts==old);
 busy=0;valid=0;result=0xbeef;
 assert(!native_riu_access(1,3,0,0,&result) && result==0xbeef);
 valid=1;error=1;assert(!native_riu_access(1,3,0,1,&result));
 assert(!native_riu_access(8,3,0,0,&result));
 assert(native_tap_wait());tap_valid=0;assert(!native_tap_wait());
 return 0;
}
''')

    def test_sdram_init_failure_ownership_and_normal_handoff(self):
        source = (ROOT / "litex/soc/software/liblitedram/sdram.c").read_text()
        start = source.index("int sdram_init(void) {")
        function = source[start:source.index("\n}\n", start) + 3]
        self.compile_run(r"""
#include <assert.h>
#include <stdio.h>
#define CONFIG_SDRAM_USNATIVE_XEM8320
#define CSR_DDRCTRL_BASE 1
#define MAIN_RAM_BASE 0x40000000ul
#define MAIN_RAM_BASE_VA MAIN_RAM_BASE
#define MEMTEST_DATA_SIZE 64
#define false 0
static unsigned calibration_ok, memory_ok=1, handoffs, tests, speeds, failed, done, status_error;
static int sdram_usnative_init(void) {return calibration_ok;}
static unsigned ddrphy_training_error_read(void) {return 7;}
static unsigned nb_fail(unsigned code) {failed=code;return code;}
static void sdram_software_control_off(void) {++handoffs;}
static void ddrctrl_init_done_write(unsigned value) {done=value;}
static void ddrctrl_init_error_write(unsigned value) {status_error=value;}
static int memtest(unsigned *p, unsigned size) {(void)p;(void)size;++tests;return memory_ok;}
static void memspeed(unsigned *p,unsigned size,int write,int random) {(void)p;(void)size;(void)write;(void)random;++speeds;}
""" + function + r"""
int main(void) {
 assert(!sdram_init() && failed==7 && !handoffs && !tests && done && status_error);
 calibration_ok=1;failed=0;memory_ok=0;
 assert(!sdram_init() && failed==20 && handoffs==1 && tests==1 && !speeds && done && status_error);
 failed=0;memory_ok=1;
 assert(sdram_init() && !failed && handoffs==2 && tests==2 && speeds==1 && done && !status_error);
 return 0;
}
""")

    def test_component_phy_dma_admission_tracks_full_initialization(self):
        source = (ROOT / "litex/soc/software/liblitedram/sdram.c").read_text()
        start = source.index("int sdram_init(void) {")
        function = source[start:source.index("\n}\n", start) + 3]
        self.compile_run(r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
#define SDRAM_PHY_USPDDRPHY
#define CSR_DDRCTRL_BASE 1
#define CSR_DDRPHY_RST_ADDR 1
#define CSR_DDRPHY_WDLY_DQS_INC_COUNT_ADDR 1
#define SDRAM_PHY_WRITE_LEVELING_CAPABLE
#define SDRAM_PHY_MODULES 2
#define write_rst_dqs_delay 7
#define MAIN_RAM_BASE 0x40000000ul
#define MAIN_RAM_BASE_VA MAIN_RAM_BASE
#define MEMTEST_DATA_SIZE 64
#define false 0
static unsigned memory_ok=1, dqs_ok=1, leveling_ok=1, admission=9, admission_writes, tests, initialized, events;
static char order[64];
static void dma_bench_software_ready_write(unsigned value) {admission=value;++admission_writes;}
static void ddrctrl_init_done_write(unsigned value) {(void)value;}
static void ddrctrl_init_error_write(unsigned value) {(void)value;}
static void sdram_write_leveling_rst_cmd_delay(unsigned value) {(void)value;}
static void sdram_write_leveling_rst_dat_delay(unsigned module, unsigned show) {(void)module;(void)show;}
static void sdram_software_control_on(void) {order[events++]='O';}
static void sdram_software_control_off(void) {}
static int sdram_leveling(void) {return leveling_ok;}
static int selected;
static void sdram_select(int module, int dq) {assert(dq==0);selected=module;}
static void sdram_deselect(int module, int dq) {assert(module==selected && dq==0);}
static int write_rst_dqs_delay_checked(int module) {
 assert(module==selected); order[events++]=module?'1':'0'; return dqs_ok;
}
static void ddrphy_rst_write(unsigned value) {order[events++]=value?'R':'r';}
static void cdelay(unsigned value) {(void)value;order[events++]='D';}
static void init_sequence(void) {++initialized;order[events++]='J';}
static int memtest(unsigned *p, unsigned size) {(void)p;(void)size;++tests;return memory_ok;}
static void memspeed(unsigned *p,unsigned size,int write,int random) {(void)p;(void)size;(void)write;(void)random;}
""" + function + r"""
int main(void) {
 assert(sdram_init() && admission==1 && admission_writes==2 && tests==1 && initialized==1);
 assert(events>=8 && !memcmp(order, "O01RDrDJ", 8));
 memory_ok=0;
 assert(!sdram_init() && admission==0 && admission_writes==3 && tests==2 && initialized==2);
 memory_ok=1; dqs_ok=0;
 assert(!sdram_init() && admission==0 && admission_writes==4 && tests==2 && initialized==2);
 dqs_ok=1; leveling_ok=0;
 assert(!sdram_init() && admission==0 && admission_writes==5 && tests==2 && initialized==3);
 return 0;
}
""")

    def test_write_leveling_failure_stops_later_training(self):
        source = (ROOT / "litex/soc/software/liblitedram/sdram.c").read_text()
        start = source.index("int sdram_leveling(void) {")
        function = source[start:source.index("\n}\n", start) + 3]
        self.compile_run(r"""
#include <assert.h>
#include <stdio.h>
#define SDRAM_PHY_USPDDRPHY
#define SDRAM_PHY_MODULES 1
#define DQ_COUNT 1
#define SDRAM_PHY_WRITE_LEVELING_CAPABLE
#define SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE
#define SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE
#define SDRAM_PHY_READ_LEVELING_CAPABLE
static unsigned write_ok, write_calls, latency_calls, write_dq_calls, read_calls, released;
static void write_rst_delay(int module) {(void)module;}
static void read_rst_dq_delay(int module) {(void)module;}
static void sdram_leveling_action(int module, int dq, void (*action)(int)) {(void)dq;action(module);}
static void sdram_software_control_on(void) {}
static void sdram_software_control_off(void) {released++;}
static int sdram_write_leveling(void) {write_calls++;return write_ok;}
static void sdram_write_latency_calibration(void) {latency_calls++;}
static void sdram_write_dq_dqs_training(void) {write_dq_calls++;}
static void sdram_read_leveling(void) {read_calls++;}
""" + function + r"""
int main(void) {
 assert(!sdram_leveling());
 assert(write_calls==1 && !latency_calls && !write_dq_calls && !read_calls);
 assert(released==1);
 write_ok=1;
 assert(sdram_leveling());
 assert(write_calls==2 && latency_calls==1 && write_dq_calls==1 && read_calls==1);
 assert(released==2);
 return 0;
}
""")

    def test_component_phy_debug_maps_only_standard_training_details(self):
        source = (ROOT / "litex/soc/software/liblitedram/sdram.c").read_text()
        self.assertIn("#ifdef CONFIG_SDRAM_PHY_DEBUG", source)
        block = source.split("#ifdef CONFIG_SDRAM_PHY_DEBUG", 1)[1].split("#endif", 1)[0]
        self.assertIn("#define SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG", block)
        self.assertIn("#define SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG", block)
        self.assertNotIn("USNATIVE", block)

    def test_component_phy_memory_test_cannot_grant_dma(self):
        source = (ROOT / "litex/soc/software/bios/cmds/cmd_litedram.c").read_text()
        start = source.index("static void sdram_test_handler(")
        function = source[start:source.index("\n}\n", start) + 3]
        self.compile_run(r"""
#include <assert.h>
#define CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
#define MAIN_RAM_BASE_VA 0x40000000ul
#define MAIN_RAM_SIZE 0x08000000ul
static unsigned ready, memory_ok=1;
static unsigned dma_bench_software_ready_read(void) {return ready;}
static void dma_bench_software_ready_write(unsigned value) {ready=value;}
static int memtest(unsigned *p, unsigned long size) {(void)p;(void)size;return memory_ok;}
""" + function + r"""
int main(void) {
 sdram_test_handler(0, 0); assert(!ready);
 ready=1; sdram_test_handler(0, 0); assert(ready);
 memory_ok=0; sdram_test_handler(0, 0); assert(!ready);
 return 0;
}
""")

    def test_deskew_seeds_memory_with_debug_disabled(self):
        source = (INCLUDE / "native_bit_calibration.h").read_text()
        start = source.index("static unsigned nd_calibrate(")
        function = source[start:]
        self.compile_run(r"""
#include <assert.h>
struct nd_score {unsigned errors[16];};
static unsigned seeded, writes, stage;
#define USNATIVE_DEBUG(...) do {} while (0)
#define USNATIVE_SNAPSHOT() do {} while (0)
static unsigned nd_check(struct nd_score *score, unsigned readonly) {
 if(readonly) assert(seeded); else {seeded=1; ++writes;}
 for(unsigned i=0;i<16;++i) score->errors[i]=0;
 return 0;
}
static void ddrphy_training_stage_write(unsigned value) {stage=value;}
static void sdram_software_control_off(void) {}
static int nc_set_rx(unsigned lane, unsigned tap) {(void)lane;(void)tap;return 1;}
static unsigned nb_fail(unsigned error) {return error;}
static int nd_program(unsigned *centers,unsigned lanes,int offset) {
 (void)centers;(void)lanes;(void)offset; return 1;
}
""" + function + r"""
int main(void) {
 unsigned centers[16];
 assert(nd_calibrate(3,centers)==0);
 assert(writes==5 && stage==5);
 return 0;
}
""")

    def test_ddr_rate_does_not_overflow_signed_int(self):
        source = (ROOT / "litex/soc/software/liblitedram/sdram.c").read_text()
        start = source.index("unsigned int sdram_get_freq(void) {")
        function = source[start:source.index("\n}\n", start) + 3]
        for clock in (300000000, 333333333, 366666666, 400000000):
            self.compile_run("#define SDRAM_PHY_XDR 2\n#define SDRAM_PHY_PHASES 4\n"
                + f"#define CONFIG_CLOCK_FREQUENCY {clock}\n" + function
                + f"int main(void) {{return sdram_get_freq() != {clock * 8}u;}}")
