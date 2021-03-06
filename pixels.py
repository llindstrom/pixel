"""Using Python to prototype a pixel manipulation template language

Special case: pixelcopy.
"""

# Template Types

class Surface:
    class Column:
        def __init__(self, surf, r):
            self.surf = surf
            self.r = r

    class Pixel:
        def __init__(self, surf, r, c):
            self.surf = surf
            self.posn = r, c

        @property
        def pixel(self):
            return self.surf.get_at(self.posn)

        @pixel.setter
        def pixel(self, v):
            self.surf.set_at(self.posn, int(v))
    
    @classmethod
    def get_row_iter(cls, surf):
        for r in range(surf.get_height()):
            yield cls.Column(surf, r)

    @classmethod
    def get_pix_iter(cls, row):
        for c in range(row.surf.get_width()):
            yield cls.Pixel(row.surf, row.r, c)

class PixelArray:
    class Column:
        def __init__(self,array, r):
            self.array = array
            self.r = r

    class Element:
        def __init__(self, array, r, c):
            assert(array.ndim == 2)
            self.array = array
            self.posn = r, c

        def __int__(self):
            r, c = self.posn
            return int(self.array[r, c])

        @property
        def value(self):
            r, c = self.posn
            return self.array[r, c]

        @value.setter
        def value(self, value):
            r, c = self.posn
            self.array[r, c] = value

    @classmethod
    def get_row_iter(cls, arr):
        for r in range(arr.shape[0]):
            yield cls.Column(arr, r)

    @classmethod
    def get_pix_iter(cls, row):
        for c in range(row.array.shape[1]):
            yield cls.Element(row.array, row.r, c)

# Decorators

def blitter(src_type, dst_type):
    def wrap(fn):
        def wrapper(s : src_type, d : dst_type):
            next_col_s = scc_type.get_col_iter(s)
            next_col_d = dst_type.get_col_iter(d)
            for sc, dc in zip(next_col_s, next_col_d):
                next_pix_s = scc_type.get_pix_iter(sc)
                next_pix_d = dst_type.get_pix_iter(dc)
                for sp, dp in zip(next_pix_s, next_pix_d):
                    fn(sp, dp)

        return wrapper

    return wrap
