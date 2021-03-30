import expand
import blitkit
import numpy

source = """\
@blitkit.blitter(blitkit.Array2, blitkit.Array2)
def foo(s, d):
    d.pixel = s
"""

symtab = {'blitkit': blitkit}
python_source = expand.expand(source, '<str>', symtab)
print(python_source)
code = compile(python_source, '<python_source>', 'exec')
glbs = {}
exec(code, glbs)
foo = glbs['foo']
print(list(foo.__globals__.keys()))

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
