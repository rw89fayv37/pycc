from pycc.py2ir import Py2IR
from pycc.ssair.irassembler_x64 import IRAssemblerX64
from pycc import pycc
import inspect
import ast


@pycc.compile
def return_const() -> float:
    return 10.0


@pycc.compile
def return_var(x: float) -> float:
    return x


@pycc.compile
def return_mult(x: float) -> float:
    return 2.0 * x * x


def test_return_const():
    assert return_const() == 10.0


def test_return_var():
    assert return_var(10.0) == 10.0


def test_return_mult():
    assert return_mult(10.0) == 20.0


if __name__ == "__main__":
    test_return_const()
    test_return_const()
