# Develop template instantiation
#
# TODO: Find way to add globals from type templates Surface and PixelArray
#
from . import astkit
from .astkit import BuildError
from .support import Surface, Array2, Pointer, Pixel
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

    def make_tree(self, fn_ast, arg_types):
        raise NotImplementedError("Abstract base function")

class C_Iterators(BlitterFactory):
    def make_tree(self, fn_ast, arg_types):
        check_no_returns(fn_ast)
        fn_name = fn_ast.name
        fn_args = [a.arg for a in fn_ast.args.args]
        loop_indices = self.loop_indices
        ndims = len(loop_indices)

        if ndims != 2:
            msg = "Only 2 dimensional arrays supported so far"
            raise NotImplementedError(msg)
        if len(fn_args) != 2:
            msg = "Only 2 function argments supported so far"
            raise NotImplementedError(msg)
        typed_args = [f'{n}__0' for n in fn_args]
        arg_ptrs = [f'{n}_ptr_0' for n in fn_args]
        b = astkit.TreeBuilder()
        b.identifier(fn_name)
        b.arguments()
        b.arg(fn_args[0], arg_types[0].full_name)
        b.arg(fn_args[1], arg_types[1].full_name)
        b.end()
        b.FunctionDef()

        # Array dimensions and starting points
        b.Name(arg_types[0].full_name)
        b.Call()
        b.Name(fn_args[0])
        b.end()
        b.Name(typed_args[0])
        b.Assign1()
        b.Name(arg_types[1].full_name)
        b.Call()
        b.Name(fn_args[1])
        b.end()
        b.Name(typed_args[1])
        b.Assign1()
        get_dims(b, ndims, arg_types[0], typed_args[0])
        get_byte_pointer(b, arg_types[0], typed_args[0])
        b.Name(arg_ptrs[0])
        b.Assign1()
        get_byte_pointer(b, arg_types[1], typed_args[1])
        b.Name(arg_ptrs[1])
        b.Assign1()

        # Pointer increments
        get_strides(b, ndims, arg_types[0], fn_args[0])
        get_strides(b, ndims, arg_types[1], fn_args[1])
        get_delta(b, loop_indices[0], loop_indices[1], fn_args[0])
        get_delta(b, loop_indices[0], loop_indices[1], fn_args[1])

        # Loop over outer index
        i = loop_indices[0]
        b.Name(arg_ptrs[0])
        b.Name(f'{fn_args[0]}_stride_{i}')
        b.Name(f'dim_{i}')
        b.Mult()
        b.Add()
        b.Name(f'{fn_args[0]}_end_{i}')
        b.Assign1()
        b.Name(arg_ptrs[0])
        b.Name(f'{fn_args[0]}_end_{i}')
        b.Lt()
        b.While()

        # Loop over inner index
        i = loop_indices[1]
        b.Name(arg_ptrs[0])
        b.Name(f'{fn_args[0]}_stride_{i}')
        b.Name(f'dim_{i}')
        b.Mult()
        b.Add()
        b.Name(f'{fn_args[0]}_end_{i}')
        b.Assign1()
        b.Name(arg_ptrs[0])
        b.Name(f'{fn_args[0]}_end_{i}')
        b.Lt()
        b.While()
        inline_call(b, fn_ast)
        cast_to_pixel(b, arg_types[0], typed_args[0], arg_ptrs[0])
        cast_to_pixel(b, arg_types[1], typed_args[1], arg_ptrs[1])
        b.end()
        b.Name(f'{fn_args[0]}_stride_{i}')
        b.Name(arg_ptrs[0])
        b.IAdd()
        b.Name(f'{fn_args[1]}_stride_{i}')
        b.Name(arg_ptrs[1])
        b.IAdd()
        b.end()  # inner loop

        i = loop_indices[0]
        b.Name(f'{fn_args[0]}_delta_{i}')
        b.Name(arg_ptrs[0])
        b.IAdd()
        b.Name(f'{fn_args[1]}_delta_{i}')
        b.Name(arg_ptrs[1])
        b.IAdd()
        b.end()  # outer loop

        b.end()  # function do_blit
        return b.pop()

def get_dims(build, ndims, typ, name):
    build.Name(name)
    build.Attribute('shape')
    build.Tuple()
    for i in range(ndims):
        build.Name(f'dim_{i}')
    build.end()
    build.Assign1()

def get_byte_pointer(build, typ, name):
    build.Name('ctypes.c_char')
    build.Name('loops.Pointer')
    build.Subscript()
    build.Call()
    build.Name(name)
    build.Attribute('pixels_address')
    build.end()

def get_strides(build, ndims, typ, name):
    build.Name(f'{name}__0')
    build.Attribute('strides')
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

def cast_to_pixel(build, pixels_type, pixels_name, ptr_name):
    build.Name(pixels_name)
    build.Attribute('format')
    build.Name('loops.Pixel')
    build.Subscript()
    build.Call()
    build.Name(ptr_name)
    build.end()

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
                build.Name(f'{name}__1')
                build.Assign1()
            elif counts[name] == 1:
                replace[name] = value
        replace_name(body, replace)
        change_id(body, arg_names)
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

def change_id(body, arg_names):
    if arg_names:
        change = ChangeId(arg_names)
        for stmt in body:
            change.visit(stmt)

class ChangeId(ast.NodeVisitor):
    def __init__(self, arg_names):
        self.arg_names = set(arg_names)

    def visit_Name(self, node):
        if node.id in self.arg_names:
            node.id = f'{node.id}__1'
        
blitter = Blitter(C_Iterators, [1, 0])

def inline_decorators(module, symtab):
    """Replace decorators with inlined code"""

    symtab = symtab.copy()
    for i in range(len(module.body)):
        stmt = module.body[i]
        if isinstance(stmt, ast.FunctionDef):
            for d in reversed(stmt.decorator_list):
                module.body[i] = evaluate(d, symtab)(stmt)

def evaluate(node, symtab):
    """eval a simple ast expression"""

    if isinstance(node, ast.Name):
        # Get value
        try:
            return symtab[node.id]
        except KeyError:
            msg = f"Name {node.id} not in symbol table"
            raise loops.BuildError(msg)
    elif isinstance(node, ast.Attribute):
        # Get attribute
        value = evaluate(node.value, symtab)
        return getattr(value, node.attr)
    elif isinstance(node, ast.Call):
        # call function
        func = evaluate(node.func, symtab)
        args = [evaluate(a, symtab) for a in node.args]
        return func(*args)
    elif isinstance(node, ast.Subscript):
        value = evaluate(node.value, symtab)
        key = evaluate(node.slice, symtab)
        return value[key]
    else:
        msg = "Unknown expression element {node}"
        raise loops.BuildError(msg)

# This is what should be generated for
#
#     @loops.blitter(loops.Array2, loops.Surface)
#     def do_blit(s, d):
#         pass
#     
# Function globals are:
#     loops.Surface, loops.Array2, loops.Pointer, loops.Pixel
#     ctypes.c_char
#
def do_blit(s, d):
    # Array dimensions and starting points
    s__0 = loops.Array2(s)
    d__0 = loops.Surface(d)
    dim_0, dim_1 = loops.Array2.shape(s__0)
    s_ptr_0 = loops.Pointer[ctypes.c_char](s__0.pixels_address)
    d_ptr_0 = loops.Pointer[ctypes.c_char](d__0.pixels_address)

    # Pointer increments
    s_stride_0, s_stride_1 = s__0.strides
    d_stride_0, d_stride_1 = d__0.strides
    s_delta_1 = s_stride_1 - s_stride_0 * dim_0
    d_delta_1 = d_stride_1 - d_stride_0 * dim_0

    # Loop over index 1...
    s_end_1 = s_ptr_0 + s_stride_1 * dim_1
    while s_ptr_0 < s_end_1:
        # Loop over index 0...
        s_end_0 = s_ptr_0 + s_stride_0 * dim_0
        while s_ptr_0 < s_end_0:
            loops.Pixel[d__0.format](d_ptr_0).value = loops.Pixel[s__0.format](s_ptr_0)
            s_ptr_0 += s_stride_0
            d_ptr_0 += d_stride_0

        s_ptr_0 += s_delta_1
        d_ptr_0 += d_delta_1
