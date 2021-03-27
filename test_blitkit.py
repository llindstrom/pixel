import blitkit
import pixels
import numpy

@blitkit.blitter(pixels.PixelArray, pixels.PixelArray)
def foo(s, d):
    d.pixel = s

def fill(a):
    w, h = a.shape
    for j in range(h):
        for i in range(w):
            a[i, j] = (i + 1) * 10 + (j + 1)

s = numpy.zeros((12, 9), dtype=numpy.int32)
fill(s)
d = numpy.zeros((12, 9), dtype=numpy.int32, order='F')
assert(not (s == d).any())
foo(s, d)
assert((s == d).all())
s[:, :] = 0
assert(not (s == d).any())
foo(d, s)
assert((s == d).all())
