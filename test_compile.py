import compile

src = """\
@export
def foo():
    pass

def local():
    pass

@export
def bar():
    pass

@staticmethod
def other():
    pass
"""

symtab = {'export': object()}
funcs = compile.compile(src, '<str>', symtab)
assert(len(funcs) == 2)
assert('foo' in funcs)
assert(funcs['foo'].__name__ == 'foo')
assert('bar' in funcs)
assert(funcs['bar'].__name__ == 'bar')
