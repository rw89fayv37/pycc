from pycc.py2ir import Py2IR
from pycc.ssair.irassembler_x64 import IRAssemblerX64
from pycc.ssair.irparser import IRParser
from pycc.ssair.iroptimizer import IROptimizer
from pycc import execmem
from types import FunctionType
from pathlib import Path

import os
import sys
import tempfile
import mmap
import ctypes
import ctypes.util
import ast
import inspect
import subprocess
import logging
import shutil
import resource

"""Ensure proper dependencies on file import. The dependencies required for
pycc to run are current `as` and `ld` from gnu. Maybe in the future pycc will
rid these dependencies for a python package or develop a native assembler."""
__checked = False
__gnu_as_location = None
__gnu_ld_location = None
if not __checked:
    __gnu_as_location = shutil.which("as")
    __gnu_ld_location = shutil.which("ld")

    if __gnu_as_location is None:
        raise ImportError("pycc requires gnu as to be installed")
    else:
        logging.getLogger(__name__).info("disovered gnu as... %s", __gnu_as_location)
    if __gnu_ld_location is None:
        raise ImportError("pycc requires gnu ld to be installed")
    else:
        logging.getLogger(__name__).info("disocvered gnu ld... %s", __gnu_ld_location)

    __checked = True


logger = logging.getLogger(__name__)

"""Memory mapped objects will go out of reference and be garbage collected.
These memory mapped objects will reside in this function map to keep a global
reference alive of the mmaped memory. Without this pycc will segfault when
the user calls a function who's memory has been free'ed.
"""
func_map = {}


def __get_pycache_location(func: FunctionType):
    """Obtain the __pycache__ directory to store debug and temporary files"""
    file_location = Path(inspect.getfile(func))
    pycache_dir = file_location.parent / Path(sys.implementation.cache_tag)
    return pycache_dir.parent / "__pycache__"


def __cfunctype_to_c_prototype(func: ctypes.CFUNCTYPE) -> str:
    """Helper function to convert cfunctype to a c like function def string"""
    c_str = ""
    match func.restype.__qualname__:
        case "c_double":
            c_str += "double {}("

    for arg_idx, argument in enumerate(func.argtypes):
        match argument.__qualname__:
            case "c_double":
                c_str += "double"
        if arg_idx + 1 != len(func.argtypes):
            c_str += ", "
    c_str += ");"
    return c_str


def compile(func: FunctionType):
    """Compile the python code.

    On success this function returns a function that when called will execute
    the just in time compiled code.
    """

    func_name = func.__name__
    print(f"pycc: compiling function '{func_name}'")

    artifacts = __get_pycache_location(func)
    artifacts.mkdir(parents=True, exist_ok=True)

    safe_name = Path(inspect.getfile(func)).name.split(".")[0]
    safe_name += "-" + func.__qualname__
    safe_name += "-" + func.__name__

    base_name = artifacts / safe_name

    # Try to compile the function body of the decorated function
    syntax: ast.AST = ast.parse(inspect.getsource(func))
    py2ir = Py2IR(inspect.getfile(func))
    ir = py2ir.visit(syntax)

    ir = IROptimizer(ir).ir
    with open(base_name.with_suffix(".ir"), mode="w+t") as fp:
        fp.write(IRParser.unparse(ir))

    ir_assembler = IRAssemblerX64(ir)
    ir_assembler.assemble()

    with open(base_name.with_suffix(".s"), mode="w+t") as fp:
        assembly_code = ir_assembler.asmx64.gen_gnu_as()

        fp.write(assembly_code)
        fp.flush()

        print(
            "\t",
            " ".join(
                [
                    "as",
                    "--64",
                    "-o",
                    str(base_name.with_suffix(".o").name),
                    base_name.with_suffix(".s").name,
                ]
            ),
        )
        subprocess.call(["as", "--64", "-o", str(base_name.with_suffix(".o")), fp.name])

        fp_bin = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        fp_bin.close()

        # Call linker
        print(
            "\t",
            " ".join(
                [
                    "ld",
                    "-T",
                    str("ld/jit.ld"),
                    "--oformat",
                    "binary",
                    "-o",
                    base_name.with_suffix(".bin").name,
                    base_name.with_suffix(".o").name,
                ]
            ),
        )
        subprocess.call(
            [
                "ld",
                "-T",
                Path(__file__).parent / "ld/jit.ld",
                "--oformat",
                "binary",
                "-o",
                base_name.with_suffix(".bin"),
                base_name.with_suffix(".o"),
            ]
        )

    with open(base_name.with_suffix(".bin"), "r+b") as fp:
        obj = execmem.PyObject_ExecMem()
        code = fp.read()
        obj.inject(code, py2ir.cdef)

    return obj
