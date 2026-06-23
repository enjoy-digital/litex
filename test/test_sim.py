import pytest

pytest.importorskip("vcd.gtkw")

from migen import *

from litex.gen.sim import run_simulation


class FSMDUT(Module):
    def __init__(self):
        self.done = Signal()

        self.submodules.fsm = FSM(reset_state="IDLE")
        self.fsm.act("IDLE",
            NextState("RUN")
        )
        self.fsm.act("RUN",
            self.done.eq(1)
        )


def test_run_simulation_generates_gtkw_savefile(tmp_path):
    dut  = FSMDUT()
    vcd  = tmp_path / "sim.vcd"
    gtkw = tmp_path / "sim.gtkw"

    def generator():
        yield
        assert (yield dut.done) == 1

    run_simulation(dut, generator(), vcd_name=str(vcd), gtkw_name=str(gtkw))

    assert vcd.exists()
    assert gtkw.exists()
    assert "sim.vcd" in gtkw.read_text()

    filters = list(tmp_path.glob("filter__*.txt"))
    assert len(filters) == 1
    assert "IDLE" in filters[0].read_text()
    assert "RUN" in filters[0].read_text()
