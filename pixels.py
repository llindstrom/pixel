"""Using Python to prototype a pixel manipulation template language

Special case: pixelcopy.
"""

import ast

# Template Types

class Surface:
    class Pixel:
        def __init__(self, surf, c, r):
            self.surf = surf
            self.posn = c, r

        @property
        def pixel(self):
            return self.surf.get_at_mapped(self.posn)

        @pixel.setter
        def pixel(self, p):
            color = self.surf.unmap_rgb(int(p))
            self.surf.set_at(self.posn, color)
    
    @staticmethod
    def size_of(surf):
        return surf.get_size()

    @classmethod
    def get_at(cls, surf, col, row):
        return cls.Pixel(surf, col, row)

class PixelArray:
    class Element:
        def __init__(self, array, c, r):
            assert(array.ndim == 2)
            self.array = array
            self.posn = c, r

        def __int__(self):
            c, r = self.posn
            return int(self.array[c, r])

        @property
        def value(self):
            c, r = self.posn
            return self.array[c, r]

        @value.setter
        def value(self, value):
            c, r = self.posn
            self.array[c, r] = value

    @staticmethod
    def size_of(array):
        return array.shape[0:2]

    @classmethod
    def get_at(cls, array, c, r):
        return cls.Element(array, c, r)

# Decorators

def blitter(src_type, dst_type):
    def wrap(fn):
        def wrapper(s, d):
            w, h = src_type.size_of(s)
            for c in range(w):
                for r in range(h):
                    fn(src_type.get_at(s, c, r), dst_type.get_at(d, c, r))

        return wrapper

    return wrap

'''   may use?
def loops(a, b, fn):
    body = [call('fn', ['sp', 'dp'])]
    body = [loop([('sp', a.pix_iter), ('dp', b.pix_iter)], body)]
    body = [loop([('sc', a.col_iter), ('dc', b.col_iter)], body)]
    f = function('wrapper', ['s', 'd'], body)
    return build(f, {'fn': fn})

def build(tree, bindings):
    m = module(tree)
    glob = bindings.copy()
    code = compile(m, __file__, 'exec')
    exec(code, glob)
    if isinstance(tree, ast.FunctionDef):
        return glob[tree.identifier]
    else:
        raise ValueError("Unsupported ast node {}".format(type(tree)))

def module(tree):
    return ast.Module([tree], [])

def function(name, args, body):
    arglist = [ast.arg(n) for n in args]
    return ast.arguments([], arglist, [], [], [])

def call(name, args):
    n = ast.Name(name, ast.Load())
    a = [ast.Name(x, ast.Load()) for x in args]
    return ast.Call(n, a, [], [], [])
'''
