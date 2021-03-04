from blit import Pixel, MIN

def blend_add(s: Pixel, d: Pixel) -> None:
    d.rgb = MIN(d.rgb + s.rgb, 255)
