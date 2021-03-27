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

    def __init__(self, src_type, dst_type, loop_indices):
        self.src_type = src_type
        self.dst_type = dst_type
        self.loop_indices = loop_indices

    def __call__(self, fn):
        fn_name = name_of(fn)
        tree = self.make_tree(fn_name)
        code = compile(tree, '<C_Iterator>', 'exec')
        gbls = {'src_type': self.src_type, 'dst_type': self.dst_type,
                f'{fn_name}_0': fn}
        lcls = {}
        exec(code, gbls, lcls)
        blit = lcls[fn_name]
        st_name = name_of(self.src_type)
        dt_name = name_of(self.dst_type)
        trav = ", ".join(str(i) for i in self.loop_indices)
        blit.__doc__ = (
            f"{fn_name}(s: {st_name}, d: {dt_name}) -> None\n\n"
             "Blit s to d. This version uses C pointer arithmetic only\n"
            f"to traverse over elements in index order [{trav}].")
        blit.tree = tree
        blit.wraps = fn
        return blit

    def make_tree(self, fn_name):
        raise NotImplementedError("Abstract base function")

class C_Iterators(BlitterFactory):
    def make_tree(self, fn_name):
        loop_indices = self.loop_indices
        ndims = len(loop_indices)

        if (ndims != 2):
            msg = "Only 2 dimensional arrays supported so far"
            raise NotImplementedError(msg)
        b = astkit.TreeBuilder()
        b.identifier(fn_name)
        b.arguments()
        b.identifier('s')
        b.identifier('d')
        b.end()
        b.FunctionDef()

        # Array dimensions and starting points
        get_dims(b, ndims, 'src_type', 's')
        b.Name('sp')
        b.Name('src_type')
        b.identifier('pointer')
        b.Attribute()
        b.Call()
        b.Name('s')
        b.end()
        b.Assign1()
        b.Name('dp')
        b.Name('dst_type')
        b.identifier('pointer')
        b.Attribute()
        b.Call()
        b.Name('d')
        b.end()
        b.Assign1()

        # Pointer increments
        get_strides(b, ndims, 'src_type', 's')
        get_strides(b, ndims, 'dst_type', 'd')
        get_delta(b, loop_indices[0], loop_indices[1], 's')
        get_delta(b, loop_indices[0], loop_indices[1], 'd')

        # Loop over outer index
        i = loop_indices[0]
        b.Name(f's{i}_end')
        b.Name('sp')
        b.Name(f's_stride_{i}')
        b.Name(f'd{i}')
        b.Mult()
        b.Add()
        b.Assign1()
        b.Name('sp')
        b.Name(f's{i}_end')
        b.Lt()
        b.While()

        # Loop over inner index
        i = loop_indices[1]
        b.Name(f's{i}_end')
        b.Name('sp')
        b.Name(f's_stride_{i}')
        b.Name(f'd{i}')
        b.Mult()
        b.Add()
        b.Assign1()
        b.Name('sp')
        b.Name(f's{i}_end')
        b.Lt()
        b.While()
        b.Name(f'{fn_name}_0')
        b.Call()
        b.Name('src_type')
        b.identifier('Pixel')
        b.Attribute()
        b.Call()
        b.Name('sp')
        b.end()
        b.Name('dst_type')
        b.identifier('Pixel')
        b.Attribute()
        b.Call()
        b.Name('dp')
        b.end()
        b.end()
        b.Expr()
        b.Name('sp')
        b.Name(f's_stride_{i}')
        b.IAdd()
        b.Name('dp')
        b.Name(f'd_stride_{i}')
        b.IAdd()
        b.end()  # inner loop

        i = loop_indices[0]
        b.Name('sp')
        b.Name(f's_delta_{i}')
        b.IAdd()
        b.Name('dp')
        b.Name(f'd_delta_{i}')
        b.IAdd()
        b.end()  # outer loop

        b.end()  # function do_blit
        return b.Module()

def get_dims(build, ndims, typ, name):
    build.Tuple()
    for i in range(ndims):
        build.Name(f'd{i}')
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
    build.Name(f'd{prev_index}')
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
# Function globals are src_type, dst_type and fn_0.
#
def do_blit(s, d):
    """do_blit(s: Array, d: Surface) -> None

Blit s to d. This version uses C pointer arithmetic only
to traverse over elements in index order [1, 0]."""
    # Array dimensions and starting points
    d0, d1 = src_type.size_of(s)
    sp = src_type.pointer(s)
    dp = dst_type.pointer(d)

    # Pointer increments
    s_stride_0, s_stride_1 = src_type.strides(s)
    d_stride_0, d_stride_1 = dst_type.strides(d)
    s_delta_1 = s_stride_1 - s_stride_0 * d0
    d_delta_1 = d_stride_1 - d_stride_0 * d0

    # Loop over index 1...
    s1_end = sp + s_stride_1 * d1
    while sp < s1_end:
        # Loop over index 0...
        s0_end = sp + s_stride_0 * d0
        while sp < s0_end:
            do_blit_0(src_type.Pixel(sp), dst_type.Pixel(dp))
            sp += s_stride_0
            dp += d_stride_0

        sp += s_delta_1
        dp += d_delta_1

blitter = Blitter(C_Iterators, [1, 0])
