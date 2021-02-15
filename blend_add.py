def BLEND_ADDx(s: Pixel, d: Pixel) -> NoneType:
    d.r = MIN(d.r + s.r, 255)
    d.g = MIN(d.g + s.g, 255)
    d.b = MIN(d.b + s.b, 255)