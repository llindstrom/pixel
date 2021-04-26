# This test does not properly check arithmetic

import expand_c
import loops.blitkit
import ast

source = """\
@loops.blitter(loops.Array2, loops.Array2)
def foo(s, d):
    d.pixel = (s.pixel + d.pixel) // 2

@loops.blitter(loops.Array2, loops.Surface)
def bar(s, d):
    d.pixel = s
"""

symtab = {'loops': loops.blitkit}

module_ast, symtab = expand_c.expand(source, '<str>', symtab)
python_source = ast.unparse(module_ast)

path = 'test_blitter_c.py'
with open(path, 'w', encoding='utf-8') as f:
    f.write("# Generated by test_expand.py\n\n")
    f.write(python_source)
    f.write("\n\n# Symbol Table\n#\n")
    for key, item in symtab.items():
        f.write(f"#  '{key}': {repr(item)}\n")