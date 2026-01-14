from pycc.py2ir import Py2IR
from pycc.ssair.irassembler_x64 import IRAssemblerX64
from pycc import pycc
import inspect
import ast
import time


@pycc.compile
def return_const() -> float:
    return 10.0


@pycc.compile
def return_var(x: float) -> float:
    return x


@pycc.compile
def return_mult(x: float) -> float:
    return 2.0 * x * x


@pycc.compile
def return_normalized(low: float, high: float, z: float) -> float:
    x1 = low
    y1 = 0.0

    x2 = high
    y2 = 1.0

    m = (y2 - y1) / (x2 - x1)
    # y = mx + b
    # y - mx = b
    b = y1 - (m * x1)

    return m * z + b


def test_return_const():
    assert return_const() == 10.0


def test_return_var():
    assert return_var(10.0) == 10.0


def test_return_mult():
    assert return_mult(10.0) == 200.0


def test_normalize():
    for x in [
        -1,
        -0.9,
        -0.8,
        -0.7,
        -0.6,
        -0.5,
        -0.4,
        -0.3,
        -0.2,
        -0.1,
        0.0,
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        0.7,
        0.8,
        0.9,
        1.0,
    ]:
        print(return_normalized(-1, 1, x))

    assert return_normalized(-1, 1, 0.0) == 0.5


if __name__ == "__main__":
    test_return_const()
    test_return_var()
    test_return_mult()
    test_normalize()
