"""Specialize an AST for writing as a Python module
"""

from . import astkit
import re
import ast

def inline_types(module):
    """Replace types with inlined code"""

    visitor = Inliner(inliner_symbols.copy())
    visitor.visit(module)
    add_imports(module)

def add_imports(module):
    """Insert import statements from symbol table"""

    collect_imports = ImportCollector()
    collect_imports.visit(module)
    imports = collect_imports.imports

    # Remove redundant imports
    #
    # If a submodule of a module is imported, then it is unnecessary to
    # do an import on the module, assuming no 'from' imports or 'as' clauses.
    redundant = {n
        for name in imports for n in outer_names(name) if n not in imports}
    imports -= redundant

    # Insert import statment
    if imports:
        stmt = ast.Import(names=[ast.alias(name) for name in imports])
        module.body.insert(0, stmt)

def outer_names(name):
    """Iteratate over parent import names

    'a' -> (,)
    'a.b.c' -> ('a', 'a.b')
    """
    elements = name.split('.')
    for i in range(1, len(elements)):
        yield '.'.join(elements[0:i])

# Inliner types
class IGeneric:
    def __init__(self, root_name):
        self._cache = {}
        self.root_name = root_name
        self.subscript_re = re.compile(fr'{root_name}\[([^]]+)\]')

    def subtype(self, typ_id):
        match = self.subscript_re.match(typ_id)
        if match is None:
            return None
        return match.group(1)

    def find_size(self, typ_id):
        subtype = self.subtype(typ_id)
        if subtype is None:
            return 0
        try:
            size = self._cache[subtype]
        except KeyError:
            ctype = eval(subtype)
            size = ctypes.sizeof(ctype)
            self._cache[subtype] = size
        return size

    def Subscript(self, node, symtab):
        # Assume node.slice is an ast.Name giving a fully qualified identifier
        tmpl_arg = node.slice.id
        typ_id = f"inliner.{type(self).__name__}[{tmpl_arg}]"
        loops_typ_id = f"{self.root_name}[{tmpl_arg}]"
        try:
            inliner = symtab[typ_id]
        except KeyError:
            symtab[typ_id] = self
            symtab[loops_typ_id] = typ_id
        return ast.Name(loops_typ_id, ctx=node.ctx, typ_id=loops_typ_id)

class IArray2:
    def __init__(self):
        self.build = astkit.TreeBuilder()

    def Name(self, node, symtab):
        return node

    def Call(self, node, symtab):
        # Assume class call
        return node.args[0]

    def Attribute(self, node, symtab):
        assert(isinstance(node.ctx, ast.Load))
        attr = node.attr
        b = self.build
        if attr == 'shape':
            b.push(node.value)
            b.Attribute('shape')
            new_node = b.pop()
        elif attr == 'strides':
            b.push(node.value)
            b.Attribute('strides')
            new_node = b.pop()
        elif attr == 'format':
            new_node = ast.Name('ctypes.c_long', ctx=node.ctx)
        elif attr == 'pixels_address':
            b.Constant(0)
            b.Constant('data')
            b.push(node.value)
            b.Attribute('__array_interface__')
            b.Subscript()
            b.Subscript()
            new_node = b.pop()
        else:
            msg = f"Unknown Array2 attribute {attr}"
            raise BuildError(msg)
        new_node.typ_id = node.typ_id
        return new_node

    def Assign(self, node, symtab):
        # Only single assignment supported
        assert(len(node.targets) == 1)
        if node.targets[0].typ_id != node.value.typ_id:
            typ_id_t = node.targets[0].typ_id
            typ_id_v = node.value.typ_id
            msg = f"Mismatched assigned types: {typ_id_t} = {typ_id_v}"
            raise loops.BuildError(msg)
        return node

class ISurface:
    def __init__(self):
        self.build = astkit.TreeBuilder()

    def Name(self, node, symtab):
        return node

    def Call(self, node, symtab):
        # Assume class call
        return node.args[0]

    def Attribute(self, node, symtab):
        assert(isinstance(node.ctx, ast.Load))
        attr = node.attr
        b = self.build
        if attr == 'shape':
            b.push(node.value)
            b.Attribute('get_size')
            b.Call()
            b.end()
            new_node = b.pop()
        elif attr == 'strides':
            b.Tuple()
            b.push(node.value)
            b.Attribute('get_bytesize')
            b.Call()
            b.end()
            b.push(node.value)
            b.Attribute('get_pitch')
            b.Call()
            b.end()
            b.end()
            new_node = b.pop()
        elif attr == 'format':
            new_node = ast.Name('ctypes.c_long', ctx=node.ctx)
        elif attr == 'pixels_address':
            b.push(node.value)
            b.Attribute('_pixels_address')
            new_node = b.pop()
        else:
            msg = f"Unknown Surface attribute {attr}"
            raise BuildError(msg)
        new_node.typ_id = node.typ_id
        return new_node

    def Assign(self, node, symtab):
        # Only single assignment supported
        assert(len(node.targets) == 1)
        if node.targets[0].typ_id != node.value.typ_id:
            typ_id_t = node.targets[0].typ_id
            typ_id_v = node.value.typ_id
            msg = f"Mismatched assigned types: {typ_id_t} = {typ_id_v}"
            raise loops.BuildError(msg)
        return node

class IPointer(IGeneric):
    python_type = 'int'

    def __init__(self):
        super().__init__("loops.Pointer")

    def Name(self, node, symtab):
        if self.subtype(node.typ_id) is not None:
            node.typ_id = self.python_type
            symtab[node.id] = node.typ_id
        return node

    def Call(self, node, symtab):
        # Assume __init__ call
        assert(node.typ_id.startswith("loops.Pointer["))
        assert(len(node.args) == 1)
        value = node.args[0]
        value.typ_id = self.python_type
        if isinstance(value, ast.Name):
            self.symtab[value.id] = value.typ_id
        return value

    def BinOp(self, node, symtab):
        # Assuming <pointer> op <int> arithmetic only
        assert(node.typ_id.startswith("loops.Pointer["))
        op = node.op
        right = node.right
        if isinstance(op, (ast.Add, ast.Sub)):
            size = self.find_size(node.left.typ_id)
            if size > 1:
                node.value = ast.Mult(node.right, Constant(size))
                node.value.typ_id = node.right.typ_id
                node.typ_id = self.python_type
        else:
            op_name = type(op).__name__
            raise loops.BuildError(f"Unsupported op {op_name}")
        return node

    def Compare(self, node, symtab):
        if node.left.typ_id.startswith('loops.Pointer['):
            node.left.typ_id = self.python_type
        for other in node.comparators:
            if other.typ_id.startswith('loops.Pointer['):
                other.typ_id = self.python_type
        return node

    def Assign(self, node, symtab):
        # value is a pointer
        assert(node.value.typ_id.startswith('loops.Pointer['))
        for t in node.targets:
            if t.typ_id.startswith('loops.Pointer['):
                t.typ_id = self.python_type
        return node

    def AugAssign(self, node, symtab):
        # <pointer> op= <int> arithmetic only
        assert(node.value.typ_id == 'int')
        op = node.op
        target = node.target
        if isinstance(op, (ast.Add, ast.Sub)):
            size = self.find_size(node.target.typ_id)
            if size > 1:
                node.value = ast.Mult(node.value, Constant(size))
                node.value.typ_id = node.left.value.typ_id
        else:
            op_name = type(op).__name__
            raise loops.BuildError(f"Unsupported op {op_name}")
        return node

class IPixel(IGeneric):
    """Pointer to C integer"""
    def __init__(self):
        super().__init__('loops.Pixel')
        self.build = astkit.TreeBuilder()

    def Name(self, node, symtab):
        if self.subtype(node.typ_id) is not None:
            symtab[node.id] = node.typ_id
        return node

    def Call(self, node, symtab):
        # Assume __init__ call
        assert(node.typ_id.startswith('loops.Pixel['))
        b = self.build
        subtype = self.subtype(node.func.typ_id)
        b.Name(subtype)
        b.Attribute('from_address')
        b.Call()
        b.push(node.args[0])
        b.end()
        replacement = b.pop()
        replacement.typ_id = node.typ_id
        return replacement

    def Attribute(self, node, symtab):
        attr = node.attr
        if isinstance(node.ctx, ast.Load):
            if attr == 'pixel':
                return self.cast_int(node.value)
        else:
            if attr == 'pixel':
                # ctypes.c_<int>.from_address(<ptr>).value
                subtype = self.subtype(node.value.typ_id)
                assert(subtype is not None)
                b = self.build
                b.push(node.value)
                b.Attribute('value')
                replacement = b.pop()
                replacement.ctx = ast.Store()
                replacement.typ_id = 'int'
                return replacement
        msg = f"Unknown attribute {attr}"
        raise loops.BuildError(msg)

    def cast_int(self, node):
        subtype = self.subtype(node.typ_id)
        b = self.build
        b.push(node)
        b.Attribute('value')
        replacement = b.pop()
        replacement.typ_id = 'int'
        return replacement

    def Assign(self, node, symtab):
        assert(node.value.typ_id.startswith('loops.Pixel['))
        assert(len(node.targets) == 1)
        assert(node.targets[0].typ_id == node.value.typ_id)
        return node

class IAny:
    itype_methods = {
        'Call', 'Attribute', 'Subscript', 'BinOp', 'Name',
        'Assign', 'AugAssign', 'Compare'
        }

    def __getattr__(self, attr):
        if attr in self.itype_methods:
            return self.pass_through
        msg = f"'{type(self).__name__}' object has no attribute '{attr}'"
        raise AttributeError(msg)

    @staticmethod
    def pass_through(node, symtab):
        return node

i_any = IAny()

inliner_symbols = {
    'loops.Array2': IArray2(),
    'loops.Surface': ISurface(),
    'loops.Pointer': IPointer(),
    'loops.Pixel': IPixel(),
    }

class Inliner(IAny, ast.NodeTransformer):
    def __init__(self, symbol_table):
        super().__init__()
        self.symtab = symbol_table

    def lookup(self, node):
        itype = node.typ_id
        while isinstance(itype, str):
            try:
                itype = self.symtab[itype.partition('[')[0]]
            except KeyError:
                return i_any
        return itype

    def visit_Name(self, node):
        return self.lookup(node).Name(node, self.symtab)

    def visit_Call(self, node):
        self.generic_visit(node)
        return self.lookup(node.func).Call(node, self.symtab)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        return self.lookup(node.value).Attribute(node, self.symtab)

    def visit_Subscript(self, node):
        self.generic_visit(node)
        return self.lookup(node.value).Subscript(node, self.symtab)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        return self.lookup(node.left).BinOp(node, self.symtab)

    def visit_Compare(self, node):
        self.generic_visit(node)
        return self.lookup(node.left).Compare(node, self.symtab)

    def visit_Assign(self, node):
        self.generic_visit(node)
        return self.lookup(node.value).Assign(node, self.symtab)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        return self.lookup(node.target).AugAssign(node, self.symtab)

class ImportCollector(ast.NodeVisitor):
    """Collect modules that need importing

    Constructed names will be fully qualified names.
    """
    def __init__(self):
        super().__init__()
        self.imports = set()

    def visit_Name(self, node):
        elements = node.id.split('.')
        if len(elements) > 1:
            self.imports.add('.'.join(elements[0:-1]))
