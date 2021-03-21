"""Using Python to prototype a pixel manipulation template language

Special case: pixelcopy.
"""

import ast
import ctypes

# Template Types

class Surface:
    class Pixel:
        def __init__(self, pointer):
            if pointer.addr % 4 != 0:
                raise ValueError("Pointer not aligned on word boundary")
            self.obj = pointer.obj
            self.addr = pointer.addr

        def __int__(self):
            return int(ctypes.c_long.from_address(self.addr).value)

        @property
        def pixel(self):
            return int(ctypes.c_long.from_address(self.addr).value)

        @pixel.setter
        def pixel(self, p):
            ctypes.c_long.from_address(self.addr).value = int(p)
    
    @staticmethod
    def size_of(surf):
        return surf.get_size()

    @staticmethod
    def strides(surf):
        return surf.get_bytesize(), surf.get_pitch()

    @staticmethod
    def pointer(surf):
        if surf.get_bytesize() != 4:
            raise ValueError("Only bytesize 4 surfaces supported")
        return Pointer(surf, surf._pixels_address, ctypes.c_char)

class PixelArray:
    class Pixel:
        def __init__(self, pointer):
            if pointer.addr % 4 != 0:
                raise ValueError("Pointer not aligned on word boundary")
            self.obj = pointer.obj
            self.addr = pointer.addr

        def __int__(self):
            return int(ctypes.c_long.from_address(self.addr).value)

    @staticmethod
    def size_of(array):
        return array.shape

    @staticmethod
    def strides(array):
        return array.strides

    @staticmethod
    def pointer(array):
        if array.itemsize != 4:
            raise ValueError("Only bytesize 4 array supported")
        addr = array.__array_interface__['data'][0]
        return Pointer(array, addr, ctypes.c_char)

# Decorators

def blitter(src_type, dst_type):
    def wrap(fn):
        def wrapper(s, d):
            w, h = src_type.size_of(s)
            sp = src_type.pointer(s)
            dp = dst_type.pointer(d)
            s_stride_c, s_stride_r = src_type.strides(s)
            d_stride_c, d_stride_r = dst_type.strides(d)
            if s_stride_c > s_stride_r:
                s_end = sp + w * s_stride_c
            else:
                s_end = sp + h * s_stride_r
            s_delta_r = s_stride_r - s_stride_c * w
            d_delta_r = d_stride_r - d_stride_c * w
            while (sp < s_end):
                c_end = sp + s_stride_c * w
                while (sp < c_end):
                    fn(src_type.Pixel(sp), dst_type.Pixel(dp))
                    sp += s_stride_c
                    dp += d_stride_c
                sp += s_delta_r
                dp += d_delta_r

        return wrapper

    return wrap

# Internal types

class Pointer:
    def __init__(self, obj, addr, ctype):
        self.obj = obj  # To keep alive
        self.addr = addr
        self.ctype = ctype
        self.size = ctypes.sizeof(ctype)

    def __int__(self):
        return addr

    def __add__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        addr = self.addr + self.size * other
        return Pointer(self.obj, addr, self.ctype)

    def __radd__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        addr = self.addr + self.size * other
        return Pointer(self.obj, addr, self.ctype)

    def __iadd__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        self.addr += self.size * other
        return self

    def __sub__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from a pointer")
        addr = self.addr - self.size * other
        return Pointer(self.obj, self.addr - self.size, self.ctype)

    def __rsub__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from a pointer")
        return self.size * other - self.addr

    def __isub__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from a pointer")
        self.addr -= self.dsize * other
        return self

    def __getitem__(self, key):
        if not isinstance(key, int):
            raise TypeError("Only single integer keys allowed")
        addr = self.addr + self.size * key
        return self.ctype.from_address(addr).value

    def __setitem__(self, key, value):
        if not isinstance(key, int):
            raise TypeError("Only single integer keys allowed")
        addr = self.addr + self.size * key
        self.ctype.from_address(addr).value = value

    def __eq__(self, other):
        return self.addr == other.addr

    def __ne__(self, other):
        return self.addr != other.addr

    def __lt__(self, other):
        return self.addr < other.addr

    def __le__(self, other):
        return self.addr <= other.addr

    def __gt__(self, other):
        return self.addr > other.addr

    def __ge__(self, other):
        return self.addr >= other.addr

