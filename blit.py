"""Using Python to prototype a pixel manipulation template language
"""

# Template Types
from itertools import repeat

class Group:
    """A sequence that supports some itemwise operations.
    """

    def __init__(self, items):
        self.items = list(items)

    def __str__(self):
        s = "Group({})". format(self.items)
        return s

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def map(self, fn):
        return Group((fn(x) for x in self))

    def __add__(self, other):
        if not isinstance(other, Group):
            return Group((s + other for s in self))
        return Group((s + o for s, o in zip(self, other)))

    def __sub__(self, other):
        if not isinstance(other, Group):
            return Group((s - other for s in self))
        return Group((s - o for s, o in zip(self, other)))

    def __lshift__(self, other):
        if not isinstance(other, Group):
            return Group((s << other for s in self))
        return Group((s << o for s, o in zip(self, other)))

    def __rshift__(self, other):
        if not isinstance(other, Group):
            return Group((s >> other for s in self))
        return Group((s >> o for s, o in zip(self, other)))

    def __floordiv__(self, other):
        if not isinstance(other, Group):
            return Group((s // other for s in self))
        return Group((s // o for s, o in zip(self, other)))

    def __mul__(self, other):
        if not isinstance(other, Group):
            return Group((s * other for s in self))
        return Group((s * o for s, o in zip(self, other)))

class Pixel:
    """A mutable RGBA color

    Single color elements (planes) can be accessed with attrubutes r, g, b and
    a. These single letter attribute names can be combined to access a Group
    of planes as the same time. Eg:

    g = p.rgb  # => Group([p.r, p.g, p.a])
    """

    def __init__(self, r, g, b, a=255):
        self._r = r
        self._b = b
        self._g = g
        self._a = a

    def __str__(self):
        s = "Pixel({}, {}, {}, {})".format(self._r, self._g, self._b, self._a)
        return s

    def __getattr__(self, attr):
        planes = []
        for a in attr:
            if a == 'r':
                planes.append(self._r)
            elif a == 'g':
                planes.append(self._g)
            elif a == 'b':
                planes.append(self._b)
            elif a == 'a':
                planes.append(self._a)
            else:
                raise AttributeError("Invalid attribute {}".format(attr))
        if len(planes) == 1:
            return planes[0]
        return Group(planes)

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            object.__setattr__(self, attr, value)
            return
        for a in attr:
            if a not in "rgba":
                raise AttributeError("Invalid attribute {}".format(attr))
        alen = len(attr)
        if not isinstance(value, Group):
            value = [value] * alen
        elif alen != len(value):
            raise ValueError("attribute/value mismatch")
        for a, v in zip(attr, value):
            if a == 'r':
                self._r = v
            elif a == 'g':
                self._g = v
            elif a == 'b':
                self._b = v
            else:  # 'a'
                self._a = v

class GroupFunction:
    """Wrap a function to allow it to work with groups

    If the first argument is not a Group then it is assumed non are.
    """

    def __init__(self, func):
        self.func = func

    def __call__(self, arg1, *args):
        def as_iarg(arg):
            if isinstance(arg, Group):
                if len(arg) != group_size:
                    msg_fmt = "Group size mismatch: expected {}; got {}"
                    raise ValueError(msg_fmt.format(group_size, len(arg)))
                return iter(arg)
            return repeat(arg, group_size)

        if (isinstance(arg1, Group)):
            group_size = len(arg1)
            iargs = [iter(arg1)]
            iargs.extend(as_iarg(arg) for arg in args)
            return Group(map(self.func, *iargs))
        return self.func(arg1, *args)
        
MIN = GroupFunction(min)

# alphablend equation

if (-1 >> 1) < 0:
    def ALPHA_BLEND_COMP(sC, dC, sA):
        return ((((sC - dC) * sA + sC) >> 8) + dC)
else:
    def ALPHA_BLEND_COMP(sC, dC, sA):
        return (((dC << 8) + (sC - dC) * sA + sC) >> 8)

def ALPHA_BLEND(s, d):
    sR, sG, sB, sA = s
    dR, dG, dB, dA = d
    if dA:
        dR = ALPHA_BLEND_COMP(sR, dR, sA)
        dG = ALPHA_BLEND_COMP(sG, dG, sA)
        dB = ALPHA_BLEND_COMP(sB, dB, sA)
        dA = sA + dA - ((sA * dA) // 255)
    else:
        dR = sR
        dG = sG
        dB = sB
        dA = sA
    return dR, dG, dB, dA

ALPHA_BLENDx_SRC = """\
def ALPHA_BLENDx(s: Pixel, d: Pixel) -> None:
    if d.a:
        d.rgb = ALPHA_BLEND_COMP(s.rgb, d.rgb, s.a)
        d.a = s.a + d.a - ((s.a * d.a) // 255)
    else:
        d.rgba = s.rgba
"""

exec(ALPHA_BLENDx_SRC, globals(), locals())

# blend add

def BLEND_ADD(s, d):
    sR, sG, sB, sA = s
    dR, dG, dB, dA = d
    tmp = dR + sR
    dR = tmp if tmp <= 255 else 255
    tmp = dG + sG
    dG = tmp if tmp <= 255 else 255
    tmp = dB + sB
    dB = tmp if tmp <= 255 else 255
    return dR, dG, dB, dA

BLEND_ADDx_SRC = """\
def BLEND_ADDx(s: Pixel, d: Pixel) -> None:
    d.rgb = MIN(d.rgb + s.rgb, 255)
"""

exec(BLEND_ADDx_SRC, globals(), locals())


# zero a pixel

def ZERO(d):
    return 0, 0, 0, 0

ZEROx_SRC = """\
def ZEROx(d: Pixel) -> None:
    d.rgba = 0
"""

exec(ZEROx_SRC, globals(), locals())


# rotate the color planes in a pixel.

def ROTATE(d):
    R, G, B, A = d
    return B, R, G, A

ROTATEx_SRC = """\
def ROTATEx(p : Pixel) -> None:
    p.rgb = p.brg
"""

exec(ROTATEx_SRC, globals(), locals())

