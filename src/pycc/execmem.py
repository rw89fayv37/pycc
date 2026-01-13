"""A set of helper functions to abstract away creating executable memory locations"""

import platform
import ctypes
import ctypes_mp
import ctypes.util
import resource


class PyObject_ExecMem:

    def __init__(self, addr: ctypes.c_voidp, size: ctypes.c_size_t, prot: ctypes.c_int):
        self.addr = addr
        self.size = size
        self.prot = prot

    def __call__(self):
        pass

    def __buffer__(self, flags):
        raise NotImplementedError("")

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
    ctypes.pythonapi.mprotect.argtyeps = (
        ctypes.c_voidp,
        ctypes.c_size_t,
        ctypes.c_int
    )

    MMAP_PROT_READ = ctypes.c_int(0x1)
    MMAP_PROT_WRITE = ctypes.c_int(0x2)
    MMAP_PROT_EXEC = ctypes.c_int(0x3)
    MMAP_PROT_NONE = ctypes.c_int(0x0)

    MMAP_MAP_SHARED = ctypes.c_int(0x01)
    MMAP_MAP_PRIVATE = ctypes.c_int(0x02)
    MMAP_MAP_ANONYMOUS = ctypes.c_int(0x20)

    def mprotect_exit_on_failure(obj: PyObject_ExecMem, prot: ctypes.c_int):
        mprotect_ret = ctypes.pythonapi.mprotect(obj.addr, obj.size, prot)
        if mprotect_ret == -1:
            c_str_error = "mprotect".encode("ascii")
            ctypes.pythonapi.perror(ctypes.c_char_p(c_str_error))
            exit(1)
        obj.prot = prot

    def mmap_exit_on_failure(
        addr: ctypes.c_voidp,
        length: ctypes.c_size_t,
        prot: ctypes.c_int,
        flags: ctypes.c_int,
        fd: ctypes.c_int = ctypes.c_int(-1),
        offset: ctypes.c_ssize_t = ctypes.c_ssize_t(0),
    ):
        mmap_ret = ctypes.pythonapi.mmap(addr, length, prot, flags, fd, offset)
        if mmap_ret == ctypes.c_void_p(-1).value:
            c_str_error = "mmap_error".encode("ascii")
            ctypes.pythonapi.perror(ctypes.c_char_p(c_str_error))
            exit(1)

        execmem = PyObject_ExecMem(ctypes.c_voidp(mmap_ret), length, prot)
        return execmem

    test = mmap_exit_on_failure(
        ctypes.c_null,
        resource.getpagesize(),
        MMAP_PROT_READ | MMAP_PROT_WRITE,
        MMAP_MAP_PRIVATE | MMAP_MAP_ANONYMOUS,
    )

    # mprotect_exit_on_failure(test, MMAP_PROT_READ | MMAP_PROT_WRITE | MMAP_PROT_EXEC)

    print(memoryview(test))

else:
    raise NotImplementedError("Platform is not supported")
