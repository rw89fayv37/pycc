"""A set of helper functions to abstract away creating executable memory locations"""

from pycc import ctypes_mp

import platform
import ctypes
import ctypes.util
import resource
import inspect


def print_sorry():
    print(
        """
  Unfortunatly there is currently no support for {}.
  Please submit a feature request at https://github.com/rw89fayv37/pycc.git
  to put adding support for this platform on the development track of this
  project.
        """.format(
            platform.system()
        )
    )


# PyObject *PyMemoryView_FromMemory(char *mem, Py_ssize_t len, int flags);
# PyMemoryView_FromMemory is a stable cpython api available in the stable api
# since Python 3.7
ctypes.pythonapi.PyMemoryView_FromMemory.restype = ctypes.py_object
ctypes.pythonapi.PyMemoryView_FromMemory.argtypes = (
    ctypes.c_char_p,
    ctypes.c_ssize_t,
    ctypes.c_int,
)


if platform.system() == "Linux":

    # Use the mmap(), mprotect(), and msync() functions.
    # In either case of glibc or musl builds, mmap is already exposed by the
    # pythonapi we just need to produce the function prototype
    #
    # NOTE Python does indeed provide an internal mmap library. But due to API
    # concerns and the lack of exposing functions such as mprotect() and
    # msync(), along with the inability to easily obtain the raw void*
    # reference pycc opts to instead use the ctypes ffi to call these functions.
    # In the end these will be more stable than trying to interact with the
    # Python API through ctypes to obtain the buffer object. Modifying the
    # protection through mprotect does not update the python buffer object
    # either. Making the python api approach more of a hack than an actual
    # stable method.
    #

    ctypes.pythonapi.mmap.restype = ctypes.c_voidp
    ctypes.pythonapi.mmap.argtypes = (
        ctypes.c_voidp,
        ctypes.c_size_t,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_ssize_t,
    )

    ctypes.pythonapi.mprotect.restype = ctypes.c_int
    ctypes.pythonapi.mprotect.argtypes = (ctypes.c_voidp, ctypes.c_size_t, ctypes.c_int)

    MMAP_PROT_READ = ctypes.c_int(0x1)
    MMAP_PROT_WRITE = ctypes.c_int(0x2)
    MMAP_PROT_EXEC = ctypes.c_int(0x4)
    MMAP_PROT_NONE = ctypes.c_int(0x0)

    MMAP_MAP_SHARED = ctypes.c_int(0x01)
    MMAP_MAP_PRIVATE = ctypes.c_int(0x02)
    MMAP_MAP_ANONYMOUS = ctypes.c_int(0x20)

    def mprotect_exit_on_failure(
        addr: ctypes.c_voidp, size: ctypes.c_size_t, prot: ctypes.c_int
    ):
        mprotect_ret = ctypes.pythonapi.mprotect(addr, size, prot)
        if mprotect_ret == -1:
            c_str_error = "mprotect".encode("ascii")
            ctypes.pythonapi.perror(ctypes.c_char_p(c_str_error))
            exit(1)

    def mmap_exit_on_failure(
        addr: ctypes.c_voidp,
        length: ctypes.c_size_t,
        prot: ctypes.c_int,
        flags: ctypes.c_int,
        fd: ctypes.c_int = ctypes.c_int(0),
        offset: ctypes.c_ssize_t = ctypes.c_ssize_t(0),
    ):
        mmap_ret = ctypes.pythonapi.mmap(addr, length, prot, flags, fd, offset)
        if mmap_ret == ctypes.c_void_p(-1).value:
            c_str_error = "mmap_error".encode("ascii")
            ctypes.pythonapi.perror(ctypes.c_char_p(c_str_error))
            exit(1)
        return ctypes.c_voidp(mmap_ret)

    class PyObject_ExecMem:

        def __init__(self):
            self.addr = mmap_exit_on_failure(
                ctypes.c_voidp(0),
                ctypes.c_size_t(resource.getpagesize()),
                MMAP_PROT_WRITE,
                MMAP_MAP_PRIVATE | MMAP_MAP_ANONYMOUS,
            )
            self.size = ctypes.c_size_t(resource.getpagesize())
            self.prot = MMAP_PROT_WRITE
            self.to_call = None

        def __call__(self, *args):
            return self.to_call(*args)

        def __buffer__(self, flags: int):

            # TODO check the underlying self.prot flags to ensure that this mmaped
            # region capabilities match this buffer capabilities
            memview: memoryview = ctypes.pythonapi.PyMemoryView_FromMemory(
                ctypes.c_char_p(self.addr.value),
                ctypes.c_ssize_t(self.size.value),
                ctypes.c_int(inspect.BufferFlags.WRITE),
            )

            return memview.cast("B")

        def inject(self, code: bytes, cdef: ctypes.CFUNCTYPE):

            # Obtain the memory view of this object and write the machine code to
            # it
            memoryview(self)[: len(code)] = code
            mprotect_exit_on_failure(
                self.addr, self.size, MMAP_PROT_READ | MMAP_PROT_EXEC
            )
            self.prot = MMAP_PROT_READ | MMAP_PROT_EXEC

            # Create a ctypes function
            self.to_call = cdef(self.addr.value)

            # TODO Call msync() here to sync this buffers information with
            # possibly other readers

else:
    print_sorry()
    exit(1)
