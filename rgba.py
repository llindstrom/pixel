"""For Python 3.5
"""
from transform import CompileError
import ast

class CUint8:
    pass

c_uint8 = CUint8()

class RGBA:
    """[R, G, B, A]
    """

    def __init__(self, base_type):
        self.base_type = base_type
        
    def visit_Attribute(self, node):
        i = self._attr_as_index(node.attr)
        ctx = node.ctx
        new_node = ast.Subscript(node.value, ast.Index(ast.Num(i)), ctx)
        if isinstance(ctx, ast.Store):
            new_node.ttype = node.ttype
        new_node.ttype = c_uint8
        return new_node

    @staticmethod
    def _attr_as_index(attr):
        if attr == 'r':
            return 0
        if attr == 'g':
            return 1
        if attr == 'b':
            return 2
        if attr == 'a':
            return 3
        raise CompileError("Unknown attribute {}".format(attr))

class Coder(ast.NodeTransformer):
    def __init__(self, symtab):
        self.symtab = symtab

    def visit_arg(self, node):
        try:
            typ = self.symtab[node.arg]
            typ_id = type(typ).__name__
            type_name = ast.Name(typ_id, ast.Load())
            node.annotation = ast.copy_location(type_name, node.annotation)
        except AttributeError:
            pass
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            try:
                typ = self.symtab[node.value.id]
                new_node = typ.visit_Attribute(node)
                node = ast.copy_location(new_node, node)
                node.fix_missing_locations(node)
            except AttributeError:
                pass
        return node
