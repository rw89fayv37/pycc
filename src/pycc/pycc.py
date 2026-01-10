from pycc.py2ir import Py2IR
from pycc.ssair.irassembler_x64 import IRAssemblerX64
from pycc.ssair.irparser import IRParser
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
    ir_assembler = IRAssemblerX64()
    ir_assembler.assemble(ir)

    with open(base_name.with_suffix(".ir"), mode="w+t") as fp:
        fp.write(IRParser.unparse(ir))

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
        jit_memory = mmap.mmap(fp.fileno(), 0, prot=mmap.PROT_READ | mmap.PROT_EXEC)
        # Ensure jit_memory does not get free'ed by putting into a dict
        func_map[func] = (jit_memory,)

    # Get the base address of the allocated page
    # TODO Use modern python buffer API to get (void *) to mmaped memory address
    PyObject_JitMemory = ctypes.py_object(jit_memory)
    address = ctypes.c_void_p()
    length = ctypes.c_ssize_t()

    # Call the python api's PyObject_AsReadBuffer function
    ctypes.pythonapi.PyObject_AsReadBuffer(
        PyObject_JitMemory, ctypes.byref(address), ctypes.byref(length)
    )

    print("\t", f"mmaped executable space to {hex(id(address))}")
    jit_function_callable = py2ir.cdef(address.value)

    print(
        "\t function has been mapped to '",
        __cfunctype_to_c_prototype(py2ir.cdef).format(func_name),
        "'",
    )

    # Wrap this function to call the mmaped jit compiled function
    # instead of the original python interpreted source
    def jit_function_wrapper(*args, **kwargs):
        return jit_function_callable(*args)

    return jit_function_wrapper
