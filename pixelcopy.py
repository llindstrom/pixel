import loops

@loops.blitter(loops.Array2, loops.Surface)
def array2_to_surface(src, dst):
    dst.pixel = src

#@blitter(RGB_Array, SDL_Surface)
#def array3_to_surface(src : RGB, dst : Pixel) -> None:
#    dst.rgb = src
#    dst.a = 255
#
#@blitter(RGBA_Array, SDL_Surface)
#def arrayRGBA_to_surface(src : RGBA, dst : Pixel) -> None:
#    dst.rgba = src
