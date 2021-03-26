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
        raise NotImplementedError("abstract base class")

class C_Iterators(BlitterFactory):
    def __call__(self, fn):
        src_type = self.src_type
        dst_type = self.dst_type
        loop_indices = self.loop_indices
        ndims = len(loop_indices)

        if (ndims != 2):
            msg = "Only 2 dimensional arrays supported so far"
            raise NotImplementedError(msg)
        build = astkit.TreeBuilder()
        (build
            .identifier('do_blit')
            .arguments().identifier('s').identifier('d').end()
            .FunctionDef())
        get_dims(build, ndims, 'src_type', 's')
        (build
            .Name('sp')
            .Name('src_type').identifier('pointer').Attribute()
            .Call().Name('s').end()
            .Assign1()
            .Name('dp')
            .Name('dst_type').identifier('pointer').Attribute()
            .Call().Name('d').end()
            .Assign1())
        get_strides(build, ndims, 'src_type', 's')
        get_strides(build, ndims, 'dst_type', 'd')
        i = loop_indices[0]
        (build
            .Name('s_end')
            .Name('sp').Name(f'd{i}').Name(f's_stride_{i}').Mult().Add()
            .Assign1())
        get_delta(build, loop_indices[0], loop_indices[1], 's')
        get_delta(build, loop_indices[0], loop_indices[1], 'd')
        (build
            .Name('sp').Name('s_end').Lt()
            .While())
        i = loop_indices[1]
        (build
            .Name(f'sd{i}_end')
            .Name('sp').Name(f's_stride_{i}').Name(f'd{i}').Mult().Add()
            .Assign1()
            .Name('sp').Name(f'sd{i}_end').Lt()
            .While()
            .Name('fn').Call()
            .Name('src_type').identifier('Pixel').Attribute()
            .Call().Name('sp').end()
            .Name('dst_type').identifier('Pixel').Attribute()
            .Call().Name('dp').end()
            .end().Expr()
            .Name('sp').Name(f's_stride_{i}').IAdd()
            .Name('dp').Name(f'd_stride_{i}').IAdd()
            .end())
        i = loop_indices[0]
        (build
            .Name('sp').Name(f's_delta_{i}').IAdd()
            .Name('dp').Name(f'd_delta_{i}').IAdd()
            .end()
            .end())
        tree = build.Module()

        code = compile(tree, '<BlitFactory>', 'exec')
        gbls = {'src_type': src_type, 'dst_type': dst_type, 'fn': fn}
        lcls = {}
        exec(code, gbls, lcls)
        do_blit = lcls['do_blit']
        do_blit.tree = tree
        return do_blit
        
def get_dims(build, ndims, typ, name):
    build.Tuple()
    for i in range(ndims):
        build.Name(f'd{i}')
    build.end()
    (build
        .Name(typ).identifier('size_of').Attribute().Call().Name(name).end()
        .Assign1())

def get_strides(build, ndims, typ, name):
    build.Tuple()
    for i in range(ndims):
        build.Name(f'{name}_stride_{i}')
    build.end()
    (build
        .Name(typ).identifier('strides').Attribute().Call().Name(name).end()
        .Assign1())

def get_delta(build, index, prev_index, name):
    (build
        .Name(f'{name}_delta_{index}')
        .Name(f'{name}_stride_{index}')
        .Name(f'{name}_stride_{prev_index}')
        .Name(f'd{prev_index}')
        .Mult()
        .Sub()
        .Assign1())

# This is what should be generated for (C_Iterators, [1, 0]),
# with src_type, dst_type and fn as globals to the function.
def do_blit(s, d):
    d0, d1 = src_type.size_of(s)
    sp = src_type.pointer(s)
    dp = dst_type.pointer(d)
    s_stride_0, s_stride_1 = src_type.strides(s)
    d_stride_0, d_stride_1 = dst_type.strides(d)

    # Loop over index 1...
    s_end = sp + d1 * s_stride_1
    s_delta_1 = s_stride_1 - s_stride_0 * d0
    d_delta_1 = d_stride_1 - d_stride_0 * d0
    while sp < s_end:

        # Loop over index 0...
        sd0_end = sp + s_stride_0 * d0
        while sp < sd0_end:
            fn(src_type.Pixel(sp), dst_type.Pixel(dp))
            sp += s_stride_0
            dp += d_stride_0

        sp += s_delta_1
        dp += d_delta_1

blitter = Blitter(C_Iterators, [1, 0])
