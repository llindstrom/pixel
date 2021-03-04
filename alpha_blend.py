from C import macro
from blit import blitter, Pixel

if (-1 >> 1) < 0:
    @macro
    def ALPHA_BLEND_COMP(sC, dC, sA):
        return ((((sC - dC) * sA + sC) >> 8) + dC)
else:
    @macro
    def ALPHA_BLEND_COMP(sC, dC, sA):
        return (((dC << 8) + (sC - dC) * sA + sC) >> 8)

@blitter
def alpha_blend(s: Pixel, d: Pixel) -> None:
    if d.a:
        d.rgb = ALPHA_BLEND_COMP(s.rgb, d.rgb, s.a)
        d.a = s.a + d.a - ((s.a * d.a) // 255)
    else:
        d.rgba = s.rgba
