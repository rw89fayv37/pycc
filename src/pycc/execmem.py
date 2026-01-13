"""A set of helper functions to abstract away creating executable memory locations"""

import platform
import ctypes
import ctypes_mp
import ctypes.util
import resource


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

    MMAP_PROT_READ = ctypes.c_int(0x1)
    MMAP_PROT_WRITE = ctypes.c_int(0x2)
    MMAP_PROT_EXEC = ctypes.c_int(0x3)
    MMAP_PROT_NONE = ctypes.c_int(0x0)

    MMAP_MAP_SHARED = ctypes.c_int(0x01)
    MMAP_MAP_PRIVATE = ctypes.c_int(0x02)
    MMAP_MAP_ANONYMOUS = ctypes.c_int(0x20)

    def mmap_exit_on_failure(
        addr: ctypes.c_voidp,
        length: ctypes.c_size_t,
        prot: ctypes.c_int,
        flags: ctypes.c_int,
        fd: ctypes.c_int,
        offset: ctypes.c_ssize_t,
    ):
        mmap_ret = ctypes.pythonapi.mmap(addr, length, prot, flags, fd, offset)
        if mmap_ret == ctypes.c_void_p(-1).value:
            c_str_error = "mmap_error".encode("ascii")
            ctypes.pythonapi.perror(ctypes.c_char_p(c_str_error))
            exit(1)
        return ctypes.c_voidp(mmap_ret)

else:
    raise NotImplementedError("Platform is not supported")
