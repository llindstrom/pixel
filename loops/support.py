"""Support types to run generic AST transformation as Python

These are Python executable versions of generic loops types for testing
and development.
"""

import loops
import ctypes
import functools

# Generic Types
class Cached:
    _cache = {} 

    def __new__(cls, item, *args, **kwds):
        try:
            return Cached._cache[id(item)]
        except KeyError:
            pass
        self = object.__new__(cls)
        self.__init__(item, *args, **kwds)
        Cached._cache[id(self)] = self
        return self

class Surface(Cached):
    full_name = 'loops.Surface'

    def __init__(self, surface):
        self.surface = surface

    @property
    def shape(self):
        return self.surface.get_size()

    @property
    def strides(self):
        return self.surface.get_bytesize(), self.surface.get_pitch()

    @property
    def pixels_address(self):
        return self.surface._pixels_address

    @property
    def format(self):
        # For now, it is a ctype
        assert self.surface.get_bitsize() == 32
        assert ctypes.sizeof(ctypes.c_long) == 4
        return ctypes.c_long

class Array2(Cached):
    full_name = 'loops.Array2'

    def __init__(self, array):
        self.array = array

    @property
    def shape(self):
        return self.array.shape

    @property
    def strides(self):
        return self.array.strides

    @property
    def pixels_address(self):
        array = self.array
        if array.itemsize != 4:
            raise ValueError("Only bytesize 4 array supported")
        return array.__array_interface__['data'][0]

    @property
    def format(self):
        # For now, it is a ctype
        assert self.array.itemsize == 4
        assert ctypes.sizeof(ctypes.c_long) == 4
        return ctypes.c_long

class Generic:
    _cache = {}

    def __new__(cls, container_type):
        try:
            return cls._cache[container_type.__name__]
        except KeyError:
            c = object.__new__(cls)
            c.__init__(container_type)
            cls._cache[container_type.__name__] = c
        return c

    @property
    def __name__(self):
        return self.cls.__name__

    @property
    def __module__(self):
        return self.cls.__module__

    def __init__(self, cls):
        self.cls = cls
        self._cache = {}

    def __getitem__(self, item_type):
        return functools.partial(self.cls, item_type)

@Generic
class Pointer:
    def __init__(self, ctype, addr):
        self.full_name = f'loops.Pointer[ctypes.{ctype}]'
        self.addr = addr
        self.ctype = ctype
        self.size = ctypes.sizeof(ctype)

    def __int__(self):
        return addr

    def __add__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        addr = self.addr + self.size * other
        return Pointer[self.ctype](addr)

    def __radd__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        addr = self.addr + self.size * other
        return Pointer[self.ctype](addr)

    def __iadd__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        self.addr += self.size * other
        return self

    def __sub__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from a pointer")
        addr = self.addr - self.size * other
        return Pointer[self.ctype](addr)

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

@Generic
class Pixel:
    def __init__(self, ctype, pointer):
        if pointer.addr % 4 != 0:
            raise ValueError("Pointer not aligned on word boundary")
        self.full_name = f'loops.Pixel[ctypes.{ctype}]'
        self.ctype = ctype
        self.addr = pointer.addr

    def __int__(self):
        return int(self.ctype.from_address(self.addr).value)

    @property
    def pixel(self):
        return self.ctype.from_address(self.addr).value

    @pixel.setter
    def pixel(self, p):
        self.ctype.from_address(self.addr).value = int(p)

# Decorators

def blitter(src_type, dst_type):
    def wrap(fn):
        def wrapper(s, d):
            s_1 = src_type(s)
            d_1 = dst_type(d)
            w, h = s.shape
            sp = loops.Pointer[ctypes.c_char](s_1.pixels_address)
            dp = loops.Pointer[ctypes.c_char](d_1.pixels_address)
            s_stride_c, s_stride_r = s_1.strides
            d_stride_c, d_stride_r = d_1.strides

            # Loop over rows.
            s_end = sp + h * s_stride_r
            s_delta_r = s_stride_r - s_stride_c * w
            d_delta_r = d_stride_r - d_stride_c * w
            while (sp < s_end):
                # Loop over columns.
                r_end = sp + s_stride_c * w
                while (sp < r_end):
                    fn(loops.Pixel[s_1.format](sp),
                       loops.Pixel[d_1.format](dp)  )
                    sp += s_stride_c
                    dp += d_stride_c

                sp += s_delta_r
                dp += d_delta_r

        return wrapper

    return wrap
