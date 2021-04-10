"""Compile loop descriptions file into a Python module

Need to separate out global and local symbol tables to support multiple
module level function declarations.

Get rid of 'arg_1 = argument_1' etc.
"""

import loops.typer
import loops.python
from loops import astkit
import ast
import re
import ctypes   # For type inlining

def expand(source, path, symbol_table):
    """expand(source: str, path: string, glbs: dict) -> str
    """

    tree, typer_symtab = stage_1(source, path, symbol_table)
    return stage_2(tree), typer_symtab

def stage_1(source, path, symbol_table):
    # Stage One: General template
    symtab = symbol_table.copy()
    module_ast = ast.parse(source, path, 'exec')
    inline_decorators(module_ast, symtab)
    return module_ast, typer(module_ast, symtab)

def stage_2(module_ast):
    # Stage Two: Python code
    loops.python.inline_types(module_ast)
    return module_ast

def inline_decorators(module, symtab):
    """Replace decorators with inlined code"""

    symtab = symtab.copy()
    for i in range(len(module.body)):
        stmt = module.body[i]
        if isinstance(stmt, ast.FunctionDef):
            for d in reversed(stmt.decorator_list):
                module.body[i] = evaluate(d, symtab)(stmt)

def typer(module, symtab):
    """Add type annotation"""

    visitor = loops.typer.Typer(symtab)
    visitor.visit(module)
    return visitor.symtab

def evaluate(node, symtab):
    """eval a simple ast expression"""

    if isinstance(node, ast.Name):
        # Get value
        try:
            return symtab[node.id]
        except KeyError:
            msg = f"Name {node.id} not in symbol table"
            raise loops.BuildError(msg)
    elif isinstance(node, ast.Attribute):
        # Get attribute
        value = evaluate(node.value, symtab)
        return getattr(value, node.attr)
    elif isinstance(node, ast.Call):
        # call function
        func = evaluate(node.func, symtab)
        args = [evaluate(a, symtab) for a in node.args]
        return func(*args)
    elif isinstance(node, ast.Subscript):
        value = evaluate(node.value, symtab)
        key = evaluate(node.slice, symtab)
        return value[key]
    else:
        msg = "Unknown expression element {node}"
        raise loops.BuildError(msg)

# This is what should be generated by expand.expand for
#
#     @loops.blitter(loops.Array2, loops.Surface)
#     def do_blit(s, d):
#         d.pixel = s
#     
# Function globals are: 'ctypes'
#
import ctypes

def do_blit(arg_1: 'loops.Array2', arg_2: 'loops.Surface'):
    # Array dimensions and starting points
    dim_0, dim_1 = arg_1.shape
    parg_1 = arg_1.__array_interface__['data'][0]
    parg_2 = arg_2._pixels_address

    # Pointer increments
    (arg_1_stride_0, arg_1_stride_1) = arg_1.strides
    (arg_2_stride_0, arg_2_stride_1) = (arg_2.get_bytesize(), arg_2.get_pitch())
    arg_1_delta_1 = arg_1_stride_1 - arg_1_stride_0 * dim_0
    arg_2_delta_1 = arg_2_stride_1 - arg_2_stride_0 * dim_0

    # Loop over index 1...
    arg_1_end_1 = parg_1 + arg_1_stride_1 * dim_1
    while parg_1 < arg_1_end_1:
        # Loop over index 0...
        arg_1_end_0 = parg_1 + arg_1_stride_0 * dim_0
        while parg_1 < arg_1_end_0:
            ctypes.c_long.from_address(parg_2).value = int(ctypes.c_long.from_address(parg_1).value)
            parg_1 += arg_1_stride_0
            parg_2 += arg_2_stride_0

        parg_1 += arg_1_delta_1
        parg_2 += arg_2_delta_1
