### Taming pygame loops

This project is a prototype for a pygame loop C code generator. It takes
high level loop body descriptions and translates them into a
C library source file.

#### The Problem

The pygame package contains may loops written in C. Many of these loops perform
various blit operations between SDL surfaces. Others copy between surfaces and
objects supporting Python's new buffer protocol. They are spread out over
several pygame extension modules, and are coded in various ways.

Adding a new blit or copy options is a daunting undertaking. Not just one loop
must be written, but several, to cover the various pixel formats an SDL
surface can have. For instance, the `array_to_surface` pixelcopy method
has 18 distinct loops to copy mapped pixel values directly from an array
to a surface. These loops handle not only varying surface pixel sizes, but also
array element integer sizes, as well as the presence or absence of per-pixel
alpha. Yet there is a feature request (issue #1244) to add support for
3-dimensional RGBA arrays.

#### The Proposal

The loops are collected into a single, non-module, C shared library with
source code generated from high level loop descriptions defined in a subset
of Python. The compiler is maintained as a part of the pygame build environment.

