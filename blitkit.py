# Develop template instantiation
#
# TODO: Find way to add globals from type templates Surface and PixelArray
#
import astkit
from astkit import BuildError
import ast
import ctypes
import collections
import functools

class Blitter:
    def __init__(self, method, loop_indices):
        if len(loop_indices) != 2:
            raise ValueError("Only supports 2 dimensional arrays for now")
        self.method = method
        self.loop_indices = loop_indices

    def __call__(self, src_type, dst_type):
        return self.method(src_type, dst_type, self.loop_indices)

class BlitterFactory:
    """Base class
    
    Construct a blit loop AST that 
    """

    def __init__(self, arg1_type, arg2_type, loop_indices):
        self.arg1_type = arg1_type
        self.arg2_type = arg2_type
        self.loop_indices = loop_indices

    def __call__(self, fn_ast):
        """Inline the fn_ast within blitter loops"""
        check_arg_count(fn_ast, 2)
        check_no_returns(fn_ast)
        arg_types = [self.arg1_type, self.arg2_type]
        return self.make_tree(fn_ast, arg_types)
##        code = compile(tree, '<C_Iterator>', 'exec')
##        gbls = {f'{mangled_fn_name}': fn,
##                 'Pointer_0': pixels.Pointer, # TODO: Move elsewhere
##                 'c_char_0': ctypes.c_char, # TODO: Move elsewhere
##                 'Pixel_0': Pixel, # TODO: Move elsewhere
##                }
##        lcls = {}
##        exec(code, gbls, lcls)
##        blit = lcls[fn_name]
##        trav = ", ".join(str(i) for i in self.loop_indices)
##        blit.__doc__ = (
##            f"{fn_name}(src: {type_name_1}, dst: {type_name_2}) -> None\n\n"
##             "Blit src to dst. This version uses C pointer arithmetic only\n"
##            f"to traverse over elements in index order [{trav}].")
##        blit.tree = tree
##        blit.wraps = fn
##        return blit

    def make_tree(self, fn_ast, arg_types):
        raise NotImplementedError("Abstract base function")

class C_Iterators(BlitterFactory):
    def make_tree(self, fn_ast, arg_types):
        check_no_returns(fn_ast)
        fn_name = fn_ast.name
        loop_indices = self.loop_indices
        ndims = len(loop_indices)

        if (ndims != 2):
            msg = "Only 2 dimensional arrays supported so far"
            raise NotImplementedError(msg)
        b = astkit.TreeBuilder()
        b.identifier(fn_name)
        b.arguments()
        b.arg('arg_1', arg_types[0].full_name)
        b.arg('arg_2', arg_types[1].full_name)
        b.end()
        b.FunctionDef()

        # Array dimensions and starting points
        get_dims(b, ndims, arg_types[0], 'arg_1')
        arg_types[0].pointer(b, 'arg_1')
        b.Name('parg_1')
        b.Assign1()
        arg_types[1].pointer(b, 'arg_2')
        b.Name('parg_2')
        b.Assign1()

        # Pointer increments
        get_strides(b, ndims, arg_types[0], 'arg_1')
        get_strides(b, ndims, arg_types[1], 'arg_2')
        get_delta(b, loop_indices[0], loop_indices[1], 'arg_1')
        get_delta(b, loop_indices[0], loop_indices[1], 'arg_2')

        # Loop over outer index
        i = loop_indices[0]
        b.Name('parg_1')
        b.Name(f'arg_1_stride_{i}')
        b.Name(f'dim_{i}')
        b.Mult()
        b.Add()
        b.Name(f'arg_1_end_{i}')
        b.Assign1()
        b.Name('parg_1')
        b.Name(f'arg_1_end_{i}')
        b.Lt()
        b.While()

        # Loop over inner index
        i = loop_indices[1]
        b.Name('parg_1')
        b.Name(f'arg_1_stride_{i}')
        b.Name(f'dim_{i}')
        b.Mult()
        b.Add()
        b.Name(f'arg_1_end_{i}')
        b.Assign1()
        b.Name('parg_1')
        b.Name(f'arg_1_end_{i}')
        b.Lt()
        b.While()
        inline_call(b, fn_ast)
        arg_types[0].Pixel(b, 'parg_1')
        arg_types[1].Pixel(b, 'parg_2')
        b.end()
        b.Name(f'arg_1_stride_{i}')
        b.Name('parg_1')
        b.IAdd()
        b.Name(f'arg_2_stride_{i}')
        b.Name('parg_2')
        b.IAdd()
        b.end()  # inner loop

        i = loop_indices[0]
        b.Name(f'arg_1_delta_{i}')
        b.Name('parg_1')
        b.IAdd()
        b.Name(f'arg_2_delta_{i}')
        b.Name('parg_2')
        b.IAdd()
        b.end()  # outer loop

        b.end()  # function do_blit
        return b.pop()

def get_dims(build, ndims, typ, name):
    typ.size_of(build, name)
    build.Tuple()
    for i in range(ndims):
        build.Name(f'dim_{i}')
    build.end()
    build.Assign1()

def get_strides(build, ndims, typ, name):
    typ.strides(build, name)
    build.Tuple()
    for i in range(ndims):
        build.Name(f'{name}_stride_{i}')
    build.end()
    build.Assign1()

def get_delta(build, index, prev_index, name):
    build.Name(f'{name}_stride_{index}')
    build.Name(f'{name}_stride_{prev_index}')
    build.Name(f'dim_{prev_index}')
    build.Mult()
    build.Sub()
    build.Name(f'{name}_delta_{index}')
    build.Assign1()

def name_of(o):
    try:
        return o.__qualname__
    except AttibuteError:
        pass
    try:
        return o.__name__
    except AttributeError:
        pass
    return repr(o)

def inline_call(build, fn_ast):
    def do_inlining(args):
        if len(args) != len(arg_names):
            len1 = len(args)
            len2 = len(arg_names)
            msg = f"Inlined function takes {len2} argments: {len1} given"
            raise BuildError(msg)
        replace = dict()
        for name, value in zip(arg_names, args):
            if counts[name] > 1:
                build.push(value)
                build.Name(name)
                build.Assign1()
            elif counts[name] == 1:
                replace[name] = value
        replace_name(body, replace)
        build.push_list(body)

    arg_names = [a.arg for a in fn_ast.args.args]
    body = fn_ast.body
    counts = count_name_accesses(body)
    build.defer(do_inlining)

def check_arg_count(fn_ast, n):
    actual_n = len(fn_ast.args.args)
    if actual_n != n:
        msg = (f"expect inline function to have {n} arguments:"
               f" has {nn}")
        raise BuildError(msg)

def check_no_returns(fn_ast):
    body = fn_ast.body
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Return):
                msg = "No return statements allowed in an inlined function"
                raise BuildError(msg)
        
def count_name_accesses(body):
    return collections.Counter(n.id
        for r in body for n in ast.walk(r) if isinstance(n, ast.Name))

def replace_name(body, replacements):
    if replacements:
        rep = ReplaceName(replacements)
        for i in range(len(body)):
            body[i] = rep.visit(body[i])

class ReplaceName(ast.NodeTransformer):
    def __init__(self, replacements):
        self.replacements = replacements

    def visit_Name(self, node):
        try:
            node = self.replacements[node.id]
        except KeyError:
            pass
        return node

# Python specific inliners
class Surface:
    full_Name = 'blitkit.Surface'

    @staticmethod
    def Pixel(build, ptr_name):
        build.Name('ctypes.c_long')
        build.Name('blitkit.Pixel')
        build.Subscript()
        build.Call()
        build.Name(ptr_name)
        build.end()
    
    @staticmethod
    def size_of(build, surf_name):
        build.Name(surf_name)
        build.Attribute('get_size')
        build.Call()
        build.end()

    @staticmethod
    def strides(build, surf_name):
        build.Tuple()
        build.Name(surf_name)
        build.Attribute('get_bytesize')
        build.Call()
        build.end()
        build.Name(surf_name)
        build.Attribute('get_pitch')
        build.Call()
        build.end()
        build.end()

    @staticmethod
    def pointer(build, surf_name):
        build.Name('ctype.c_char')
        build.Name('blitkit.Pointer')
        build.Subscript()
        build.Call()
        build.Name(surf_name)
        build.Name(surf_name)
        build.Attribute('_pixels_address')
        build.end()

class Array2:
    full_name = 'blitkit.Array2'

    @staticmethod
    def Pixel(build, ptr_name):
        build.Name('ctypes.c_long')
        build.Name('blitkit.Pixel')
        build.Subscript()
        build.Call()
        build.Name(ptr_name)
        build.end()
    
    @staticmethod
    def size_of(build, array_name):
        build.Name(array_name)
        build.Attribute('shape')

    @staticmethod
    def strides(build, array_name):
        build.Name(array_name)
        build.Attribute('strides')

    @staticmethod
    def pointer(build, array_name):
        build.Name('ctypes.c_char')
        build.Name('blitkit.Pointer')
        build.Subscript()
        build.Call()
        build.Name(array_name)
        build.Constant(0)
        build.Constant('data')
        build.Name(array_name)
        build.Attribute('__array_interface__')
        build.Subscript()
        build.Subscript()
        build.end()

# Python specific classes:
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

    def __init__(self, cls):
        self.cls = cls
        self._cache = {}

    def __getitem__(self, item_type):
        return functools.partial(self.cls, item_type)

@Generic
class Pointer:
    def __init__(self, ctype, obj, addr):
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
        return type(self)(self.ctype, self.obj, addr)

    def __radd__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        addr = self.addr + self.size * other
        return type(self)(self.ctype, self.obj, addr)

    def __iadd__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only add integers to a pointer")
        self.addr += self.size * other
        return self

    def __sub__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only subtract integers from a pointer")
        addr = self.addr - self.size * other
        return type(self)(self.ctype, self.obj, self.addr - self.size)

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
        if pointer.addr % ctypes.sizeof(ctype) != 0:
            raise ValueError("Pointer not aligned on pixel boundary")
        self.from_address = ctype.from_address
        self.obj = pointer.obj
        self.addr = pointer.addr

    def __int__(self):
        return int(self.from_address(self.addr).value)

    @property
    def pixel(self):
        return int(self.from_address(self.addr).value)

    @pixel.setter
    def pixel(self, p):
        self.from_address(self.addr).value = int(p)

blitter = Blitter(C_Iterators, [1, 0])

# This is what should be generated by expand.expand for
#
#     @blitkit.blitter(blitkit.Array2, blitkit.Surface)
#     def do_blit(s, d):
#         d.pixel = s
#     
# Function globals are:
#      'blitkit.Pointer', 'ctypes.c_char', 'blitkit.Pixel', 'ctypes.c_long'
#
import blitkit, ctypes

def do_blit(arg_1: 'bitkit.Array2', arg_2: 'blitkit.Surface'):
    # Array dimensions and starting points
    dim_0, dim_1 = arg_1.shape
    parg_1 = blitkit.Pointer[ctypes.c_char](arg_1, arg_1.__array_interface__['data'][0])
    parg_2 = blitkit.Pointer[ctypes.c_char](arg_2, arg_2._pixels_address)

    # Pointer increments
    (arg_1_stride_0, arg_1_stride_1) = arg_1.strides
    (arg_2_stride_0, arg_2_stride_1) = (arg_2.get_bytesize(), arg_2.get_pitch())
    arg_1_delta_1 = arg_1_stride_1 - arg_1_stride_0 * dim_0
    arg_2_delta_1 = arg_2_stride_1 - arg_2_stride_0 * dim_0

    # Loop over index 1...
    arg_1_end_1 = parg_1 + arg_1_stride_1 * dim_1
    while parg_1 < arg_1_end_1:
        # Loop over index 0...
        arg_1_end_0 = parg_1 + arg_1_stride_0 * dim_0
        while parg_1 < arg_1_end_0:
            blitkit.Pixel[ctypes.c_long](parg_2).pixel = blitkit.Pixel[ctypes.c_long](parg_1)
            parg_1 += arg_1_stride_0
            parg_2 += arg_2_stride_0

        parg_1 += arg_1_delta_1
        parg_2 += arg_2_delta_1
