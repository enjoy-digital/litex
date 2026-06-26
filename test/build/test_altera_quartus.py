import unittest
from unittest import mock

from migen import Memory
from migen.fhdl.structure import _Fragment

from litex.build.altera.quartus import AlteraQuartusToolchain, _use_logic_style_on_small_async_read_memories


def _memory_fragment(depth=8, async_read=True, attr=None):
    memory = Memory(8, depth)
    memory.get_port(write_capable=True)
    memory.get_port(async_read=async_read)
    if attr is not None:
        memory.attr = set(attr)
    return memory, _Fragment(specials={memory})


class TestAlteraQuartus(unittest.TestCase):
    def test_ip_dir_is_none_when_quartus_is_not_found(self):
        with mock.patch("litex.build.altera.quartus.which", return_value=None):
            toolchain = AlteraQuartusToolchain()

        self.assertIsNone(toolchain.ip_dir)

    def test_ip_dir_uses_quartus_install_directory(self):
        quartus_map = "/opt/intelFPGA_lite/22.1/quartus/bin/quartus_map"

        with mock.patch("litex.build.altera.quartus.which", return_value=quartus_map):
            toolchain = AlteraQuartusToolchain()

        self.assertEqual("/opt/intelFPGA_lite/22.1/ip", toolchain.ip_dir)

    def test_small_async_read_memories_use_logic_style(self):
        memory, fragment = _memory_fragment()

        _use_logic_style_on_small_async_read_memories(fragment)

        self.assertIn(("ramstyle", "logic"), memory.attr)

    def test_sync_and_large_memories_keep_default_style(self):
        sync_memory, sync_fragment = _memory_fragment(async_read=False)
        large_memory, large_fragment = _memory_fragment(depth=64)

        _use_logic_style_on_small_async_read_memories(sync_fragment)
        _use_logic_style_on_small_async_read_memories(large_fragment)

        self.assertFalse(hasattr(sync_memory, "attr"))
        self.assertFalse(hasattr(large_memory, "attr"))

    def test_explicit_ramstyle_is_preserved(self):
        memory, fragment = _memory_fragment(attr={("ramstyle", "MLAB")})

        _use_logic_style_on_small_async_read_memories(fragment)

        self.assertEqual({("ramstyle", "MLAB")}, memory.attr)


if __name__ == "__main__":
    unittest.main()
