"""Monkey patch certain types in the ctypes library to allow for a more C like code"""
import ctypes

def ctypes_mp_int_or(self: ctypes.c_int, other: ctypes.c_int):
    """Performs integer or operation on two ctypes.c_int values"""
    return ctypes.c_int(self.value | other.value)

# Monkey Patches
ctypes.c_int.__or__ = ctypes_mp_int_or
