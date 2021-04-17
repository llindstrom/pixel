import pixelcopy as pc
import numpy as np
import pygame as pg

array = np.empty((3, 2), dtype=np.int32)
array[0, 0] = 10
array[1, 0] = 20
array[2, 0] = 30
array[0, 1] = 110
array[1, 1] = 120
array[2, 1] = 130

pg.init()
surface = pg.Surface(array.shape, 0, 32)

pc.array2_to_surface(array, surface)

assert surface.get_at_mapped((0, 0)) == 10
assert surface.get_at_mapped((1, 0)) == 20
assert surface.get_at_mapped((2, 0)) == 30
assert surface.get_at_mapped((0, 1)) == 110
assert surface.get_at_mapped((1, 1)) == 120
assert surface.get_at_mapped((2, 1)) == 130
