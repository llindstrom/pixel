# This test does not properly check arithmetic

import expand
import loops.blitkit
import numpy
import ast

source = """\
@loops.blitter(loops.Array2, loops.Array2)
def foo(s, d):
    d.pixel = (s.pixel + d.pixel) // 2
"""

symtab = {'loops': loops.blitkit}

##module_ast, symtab = expand.stage_1(source, '<str>', symtab)
module_ast, symtab = expand.expand(source, '<str>', symtab)
python_source = ast.unparse(module_ast)

path = 'test_blitter.py'
with open(path, 'w', encoding='utf-8') as f:
    f.write("# Generated by test_blitter.py\n\n")
    f.write(python_source)
    f.write("\n\n# Symbol Table\n#\n")
    for key, item in symtab.items():
        f.write(f"#  '{key}': {repr(item)}\n")

from test_blitter import foo
print(list(foo.__globals__.keys()))

def fill(a):
    w, h = a.shape
    for j in range(h):
        for i in range(w):
            a[i, j] = (i + 1) * 10 + (j + 1)

s = numpy.empty((12, 9), dtype=numpy.int32)
fill(s)
d = numpy.empty((12, 9), dtype=numpy.int32, order='F')
fill(d)
d *= 3
assert(not (s == d).any())
r = (s + d) // 2
foo(s, d)
assert((d == r).all())
