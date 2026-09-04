# SPDX-License-Identifier: BSD-2-Clause
import pytest

from litex.soc.software.bench.sim import parse_results


def output():
    rows = ["BENCH,overhead,0,0,7,00000000", "BENCH,compute,0,32768,196619,1c348001"]
    for size in [1024, 65536]:
        rows.append(f"BENCH,write,{size},{size//4},1000,00000000")
        for name in ["read_cold", "read_repeat"]:
            checksum = ((size//4)*0x12345678) & 0xffffffff
            rows.append(f"BENCH,{name},{size},{size//4},1000,{checksum:08x}")
        rows.append(f"BENCH,chase,{size},8192,1000,00000000")
    return "BENCH_BEGIN\n" + "\n".join(rows*3) + "\nBENCH_DONE\n"


def test_complete_benchmark_results():
    samples = parse_results(output())
    assert len(samples) == 10
    assert all(len(values) == 3 for values in samples.values())
    assert samples["compute_0"][0]["cycles"] == 196619


@pytest.mark.parametrize("old,new", [
    ("BENCH_DONE", ""),
    ("BENCH_BEGIN", "BENCH_ERROR,read_checksum"),
    (",196619,", ",0,"),
    (",1c348001", ",00000000"),
    ("BENCH,write,1024,256,1000,00000000", ""),
    ("BENCH,chase,1024", "BENCH,unknown,1024"),
])
def test_invalid_benchmark_results(old, new):
    with pytest.raises(ValueError):
        parse_results(output().replace(old, new))
