import unittest
import os.path
import sys
import subprocess


def _make_test_method(name, foldername):
    def test_method(self):
        filename = name + ".py"
        example_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
        filepath = os.path.join(example_path, foldername, filename)
        subprocess.check_call(
            [sys.executable, filepath],
            stdout=subprocess.DEVNULL
        )

    return test_method


class TestExamplesSim(unittest.TestCase):
    pass

for name in ("basic1",
              "basic2",
              # skip "fir" as it depends on SciPy
              # "fir",
              "memory"):
    setattr(TestExamplesSim, "test_" + name,
            _make_test_method(name, "sim"))


class TestExamplesBasic(unittest.TestCase):
    pass

for name in ("arrays",
              "fsm",
              "graycounter",
              "local_cd",
              "memory",
              "namer",
              "psync",
              "record",
              "reslice",
              "tristate",
              "two_dividers"):
    setattr(TestExamplesBasic, "test_" + name,
            _make_test_method(name, "basic"))

