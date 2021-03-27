import astkit

class Blitter:
    def __init__(self, method, loop_indices):
        if len(loop_indices) != 2:
            raise ValueError("Only supports 2 dimensional arrays for now")
        self.method = method
        self.loop_indices = loop_indices

    def __call__(self, src_type, dst_type):
        return self.method(src_type, dst_type, self.loop_indices)

class BlitterFactory:
    """Base class"""

    def __init__(self, arg1_type, arg2_type, loop_indices):
        self.arg1_type = arg1_type
        self.arg2_type = arg2_type
        self.loop_indices = loop_indices

    def __call__(self, fn):
        fn_name = name_of(fn)
        mangled_fn_name = f"{fn_name}__0"
        type_name_1 = name_of(self.arg1_type)
        mangled_type_name_1 = f"{type_name_1}__1"
        type_name_2 = name_of(self.arg2_type)
        mangled_type_name_2 = f"{type_name_2}__2"
        mangled_type_names = [mangled_type_name_1, mangled_type_name_2]
        tree = self.make_tree(fn_name, mangled_fn_name, mangled_type_names)
        code = compile(tree, '<C_Iterator>', 'exec')
        gbls = {f'{mangled_type_name_1}': self.arg1_type,
                f'{mangled_type_name_2}': self.arg2_type,
                f'{mangled_fn_name}': fn}
        lcls = {}
        exec(code, gbls, lcls)
        blit = lcls[fn_name]
        trav = ", ".join(str(i) for i in self.loop_indices)
        blit.__doc__ = (
            f"{fn_name}(src: {type_name_1}, dst: {type_name_2}) -> None\n\n"
             "Blit src to dst. This version uses C pointer arithmetic only\n"
            f"to traverse over elements in index order [{trav}].")
        blit.tree = tree
        blit.wraps = fn
        return blit

    def make_tree(self, fn_name):
        raise NotImplementedError("Abstract base function")

class C_Iterators(BlitterFactory):
    def make_tree(self, fn_name, wrapped_fn_name, type_names):
        loop_indices = self.loop_indices
        ndims = len(loop_indices)

        if (ndims != 2):
            msg = "Only 2 dimensional arrays supported so far"
            raise NotImplementedError(msg)
        b = astkit.TreeBuilder()
        b.identifier(fn_name)
        b.arguments()
        b.identifier('arg_1')
        b.identifier('arg_2')
        b.end()
        b.FunctionDef()

        # Array dimensions and starting points
        get_dims(b, ndims, type_names[0], 'arg_1')
        b.Name('parg_1')
        b.Name(type_names[0])
        b.identifier('pointer')
        b.Attribute()
        b.Call()
        b.Name('arg_1')
        b.end()
        b.Assign1()
        b.Name('parg_2')
        b.Name(type_names[1])
        b.identifier('pointer')
        b.Attribute()
        b.Call()
        b.Name('arg_2')
        b.end()
        b.Assign1()

        # Pointer increments
        get_strides(b, ndims, type_names[0], 'arg_1')
        get_strides(b, ndims, type_names[1], 'arg_2')
        get_delta(b, loop_indices[0], loop_indices[1], 'arg_1')
        get_delta(b, loop_indices[0], loop_indices[1], 'arg_2')

        # Loop over outer index
        i = loop_indices[0]
        b.Name(f'arg_1_end_{i}')
        b.Name('parg_1')
        b.Name(f'arg_1_stride_{i}')
        b.Name(f'dim_{i}')
        b.Mult()
        b.Add()
        b.Assign1()
        b.Name('parg_1')
        b.Name(f'arg_1_end_{i}')
        b.Lt()
        b.While()

        # Loop over inner index
        i = loop_indices[1]
        b.Name(f'arg_1_end_{i}')
        b.Name('parg_1')
        b.Name(f'arg_1_stride_{i}')
        b.Name(f'dim_{i}')
        b.Mult()
        b.Add()
        b.Assign1()
        b.Name('parg_1')
        b.Name(f'arg_1_end_{i}')
        b.Lt()
        b.While()
        b.Name(wrapped_fn_name)
        b.Call()
        b.Name(type_names[0])
        b.identifier('Pixel')
        b.Attribute()
        b.Call()
        b.Name('parg_1')
        b.end()
        b.Name(type_names[1])
        b.identifier('Pixel')
        b.Attribute()
        b.Call()
        b.Name('parg_2')
        b.end()
        b.end()
        b.Expr()
        b.Name('parg_1')
        b.Name(f'arg_1_stride_{i}')
        b.IAdd()
        b.Name('parg_2')
        b.Name(f'arg_2_stride_{i}')
        b.IAdd()
        b.end()  # inner loop

        i = loop_indices[0]
        b.Name('parg_1')
        b.Name(f'arg_1_delta_{i}')
        b.IAdd()
        b.Name('parg_2')
        b.Name(f'arg_2_delta_{i}')
        b.IAdd()
        b.end()  # outer loop

        b.end()  # function do_blit
        return b.Module()

def get_dims(build, ndims, typ, name):
    build.Tuple()
    for i in range(ndims):
        build.Name(f'dim_{i}')
    build.end()
    build.Name(typ)
    build.identifier('size_of')
    build.Attribute()
    build.Call()
    build.Name(name)
    build.end()
    build.Assign1()

def get_strides(build, ndims, typ, name):
    build.Tuple()
    for i in range(ndims):
        build.Name(f'{name}_stride_{i}')
    build.end()
    build.Name(typ)
    build.identifier('strides')
    build.Attribute()
    build.Call()
    build.Name(name)
    build.end()
    build.Assign1()

def get_delta(build, index, prev_index, name):
    build.Name(f'{name}_delta_{index}')
    build.Name(f'{name}_stride_{index}')
    build.Name(f'{name}_stride_{prev_index}')
    build.Name(f'dim_{prev_index}')
    build.Mult()
    build.Sub()
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

# This is what should be generated for
#
#     @blitter(Array, Surface)
#     def do_blit(s, d):
#         pass
#     
# Function globals are:
#     {'Array__1': Array, 'Surface__2': Surface, 'do_blit__0': do_blit}
#
def do_blit(arg_1, arg_2):
    """do_blit(src: Array, dst: Surface) -> None

Blit src to dst. This version uses C pointer arithmetic only
to traverse over elements in index order [1, 0]."""
    # Array dimensions and starting points
    dim_0, dim_1 = Array_1.size_of(arg_1)
    parg_1 = Array__1.pointer(arg_1)
    parg_2 = Surface__2.pointer(arg_2)

    # Pointer increments
    arg_1_stride_0, arg_1_stride_1 = Array__1.strides(a_1)
    arg_2_stride_0, arg_2_stride_1 = Surface__2.strides(a_2)
    arg_1_delta_1 = arg_1_stride_1 - arg_1_stride_0 * dim_0
    arg_2_delta_1 = arg_2_stride_1 - arg_2_stride_0 * dim_0

    # Loop over index 1...
    arg_1_end_1 = parg_1 + arg_1_stride_1 * dim_1
    while parg_1 < arg_1_end_1:
        # Loop over index 0...
        arg_1_end_0 = parg_1 + arg_1_stride_0 * dim_0
        while parg_1 < arg_1_end_0:
            do_blit__0(Array__1.Pixel(parg_1), Surface__2.Pixel(parg_2))
            parg_1 += arg_1_stride_0
            parg_2 += arg_2_stride_0

        parg_1 += arg_1_delta_1
        parg_2 += arg_2_delta_1

blitter = Blitter(C_Iterators, [1, 0])
