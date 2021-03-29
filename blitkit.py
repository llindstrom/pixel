# Develope template instantiation
#
# TODO: Find way to add globals from type templates Surface and PixelArray
#
import astkit
import pixels
import ctypes

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
        type_name_2 = name_of(self.arg2_type)
        arg_types = [self.arg1_type, self.arg2_type]
        tree = self.make_tree(fn_name, mangled_fn_name, arg_types)
        code = compile(tree, '<C_Iterator>', 'exec')
        gbls = {f'{mangled_fn_name}': fn,
                 'Pointer_0': pixels.Pointer, # TODO: Move elsewhere
                 'c_char_0': ctypes.c_char, # TODO: Move elsewhere
                 'Pixel_0': Pixel, # TODO: Move elsewhere
                }
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

    def make_tree(self, fn_name, wrapped_fn_name, arg_types):
        raise NotImplementedError("Abstract base function")

class C_Iterators(BlitterFactory):
    def make_tree(self, fn_name, wrapped_fn_name, arg_types):
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
        get_dims(b, ndims, arg_types[0], 'arg_1')
        b.Name('parg_1')
        arg_types[0].pointer(b, 'arg_1')
        b.Assign1()
        b.Name('parg_2')
        arg_types[1].pointer(b, 'arg_2')
        b.Assign1()

        # Pointer increments
        get_strides(b, ndims, arg_types[0], 'arg_1')
        get_strides(b, ndims, arg_types[1], 'arg_2')
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
        arg_types[0].Pixel(b, 'parg_1')
        arg_types[1].Pixel(b, 'parg_2')
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
    typ.size_of(build, name)
    build.Assign1()

def get_strides(build, ndims, typ, name):
    build.Tuple()
    for i in range(ndims):
        build.Name(f'{name}_stride_{i}')
    build.end()
    typ.strides(build, name)
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

class Surface:
    @staticmethod
    def Pixel(build, ptr_name):
        build.Name('Pixel_0')
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
        build.Name('Pointer_0')
        build.Call()
        build.Name(surf_name)
        build.Name(surf_name)
        build.Attribute('_pixels_address')
        build.Name('c_char_0')
        build.end()

class Array2:
    @staticmethod
    def Pixel(build, ptr_name):
        build.Name('Pixel_0')
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
        build.Name('Pointer_0')
        build.Call()
        build.Name(array_name)
        build.Name(array_name)
        build.Attribute('__array_interface__')
        build.Attribute('__getitem__')
        build.Call()
        build.Constant('data')
        build.end()
        build.Attribute('__getitem__')
        build.Call()
        build.Constant(0)
        build.end()
        build.Name('c_char_0')
        build.end()

class Pixel:
    def __init__(self, pointer):
        if pointer.addr % 4 != 0:
            raise ValueError("Pointer not aligned on word boundary")
        self.obj = pointer.obj
        self.addr = pointer.addr

    def __int__(self):
        return int(ctypes.c_long.from_address(self.addr).value)

    @property
    def pixel(self):
        return int(ctypes.c_long.from_address(self.addr).value)

    @pixel.setter
    def pixel(self, p):
        ctypes.c_long.from_address(self.addr).value = int(p)

# This is what should be generated for
#
#     @blitter(blitkit.Array2, blitkit.Surface)
#     def do_blit(s, d):
#         pass
#     
# Function globals are:
#     {'Array__1': blitkit.Array2, 'Surface__2': blitkit.Surface,
#      'do_blit__0': do_blit
#      'Pointer_0': pixels.Pointer, 'c_char_0': ctypes.c_char,
#      'Pixels_0': blitkit.Pixel }
#
def do_blit(arg_1, arg_2):
    """do_blit(src: Array, dst: Surface) -> None

Blit src to dst. This version uses C pointer arithmetic only
to traverse over elements in index order [1, 0]."""
    # Array dimensions and starting points
    dim_0, dim_1 = arg_1.shape
    parg_1 = Pointer_0(arg_1, arg_1.__array_interface__.__getitem__('data').__getitem__(0), c_char_0)
    parg_2 = Pointer_0(arg_2, arg_2._pixels_address, c_char_p)

    # Pointer increments
    (arg_1_stride_0, arg_1_stride_1) = a_1.strides
    (arg_2_stride_0, arg_2_stride_1) = (a_2.get_bytesize(), a_2.get_pitch())
    arg_1_delta_1 = arg_1_stride_1 - arg_1_stride_0 * dim_0
    arg_2_delta_1 = arg_2_stride_1 - arg_2_stride_0 * dim_0

    # Loop over index 1...
    arg_1_end_1 = parg_1 + arg_1_stride_1 * dim_1
    while parg_1 < arg_1_end_1:
        # Loop over index 0...
        arg_1_end_0 = parg_1 + arg_1_stride_0 * dim_0
        while parg_1 < arg_1_end_0:
            do_blit__0(Pixel_0(parg_1), Pixel_0(parg_2))
            parg_1 += arg_1_stride_0
            parg_2 += arg_2_stride_0

        parg_1 += arg_1_delta_1
        parg_2 += arg_2_delta_1

blitter = Blitter(C_Iterators, [1, 0])
