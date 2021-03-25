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
        raise NotImplementedError("To be implemented in subclasses")

class C_Iterators(BlitterFactory):
    def __call__(self, fn):
        src_type = self.src_type
        dst_type = self.dst_type
        loop_indices = self.loop_indices
        ndims = len(loop_indices)

        if (ndims != 2):
            raise NotImplementedError("Only 2 dimensional arrays supported so far")
        lines = ["def do_blit(s, d):", indent]
        lines += get_dims(ndims, 'src_type', 's')
        lines += ["sp = src_type.pointer(s)", "dp = dst_type.pointer(d)"]
        lines += get_strides(ndims, 'src_type', 's')
        lines += get_strides(ndims, 'dst_type', 'd')
        i = loop_indices[0]
        lines += ["", f"# Loop over index {i}..."]
        lines += [f"s_end = sp + d{i} * s_stride_{i}"]
        lines += get_delta(loop_indices[0], loop_indices[1], 's')
        lines += get_delta(loop_indices[0], loop_indices[1], 'd')
        lines += ["while sp < s_end:", indent]
        i = loop_indices[1]
        lines += ["", f"## Loop over index {i}..."]
        lines += [f"sd{i}_end = sp + s_stride_{i} * d{i}"]
        lines += [f"while sp < sd{i}_end:", indent]
        lines += ["fn(src_type.Pixel(sp), dst_type.Pixel(dp))"]
        lines += [f"sp += s_stride_{i}", f"dp += d_stride_{i}"]
        lines += [dedent, ""]
        i = loop_indices[0]
        lines += [f"sp += s_delta_{i}", f"dp += d_delta_{i}"]
        lines += [dedent, dedent]
        src = merge_lines(lines)

        code = compile(src, '<BlitFactory', 'exec')
        gbls = {'src_type': src_type, 'dst_type': dst_type, 'fn': fn}
        lcls = {}
        exec(code, gbls, lcls)
        do_blit = lcls['do_blit']
        do_blit.src = src
        return do_blit

class Delimiter:
    pass

indent = Delimiter()
dedent = Delimiter()

def get_dims(ndims, typ, name):
    dims = ", ".join(f"d{i}" for i in range(ndims))
    return [f"{dims} = {typ}.size_of({name})"]
   
def get_strides(ndims, typ, name):
    strides = ", ".join(f"{name}_stride_{i}" for i in range(ndims))
    return [f"{strides} = {typ}.strides({name})"]
 
def get_delta(index, prev_index, name):
    i = index
    pi = prev_index
    n = name
    return [f"{n}_delta_{i} = {n}_stride_{i} - {n}_stride_{pi} * d{pi}"]

def merge_lines(lines):
    def indenter():
        indentation = 0
        for line in lines:
            if line is indent:
                indentation += 4
            elif line is dedent:
                indentation -= 4
            elif indentation == 0:
                yield line
            elif indentation > 0:
                yield f"{' '*indentation}{line}"
            else:
                raise ValueError("indent/dedent count mismatch")
        if indentation != 0:
            raise ValueError("indent/dedent count mismatch")
        yield ''    # for the final linefeed

    return '\n'.join(indenter())
        
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
