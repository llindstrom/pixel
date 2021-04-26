"""Specialize an AST for writing as a C module
"""

from . import astkit, cleanup
import re
import ast

def inline_types(module):
    """Replace types with inlined code"""

    visitor = Inliner(inliner_symbols.copy())
    visitor.visit(module)
    module = cleanup.clean(module)
    add_declarations(module)

def add_declarations(module):
    """Insert variable declarations."""
    pass

##def outer_names(name):
##    """Iteratate over parent import names
##
##    'a' -> (,)
##    'a.b.c' -> ('a', 'a.b')
##    """
##    elements = name.split('.')
##    for i in range(1, len(elements)):
##        yield '.'.join(elements[0:i])

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

next_temp_id  = 0

def next_temp():
    tmp = f't_{next_temp_id}'
    next_temp_id += 1
    return tmp

class IArray2:
    def __init__(self):
        self.build = astkit.TreeBuilder()
        self._load = ast.Load()
        self._store = ast.Store()

    def Name(self, node, symtab):
        return node

    def Call(self, node, symtab):
        # Assume class call
        return node.args[0]

    def Attribute(self, node, symtab):
        assert isinstance(node.ctx, ast.Load)
        attr = node.attr
        b = self.build
        if attr == 'shape':
            b.Tuple()
            b.Constant(0)
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('shape')
            b.Subscript()
            b.Constant(1)
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('shape')
            b.Subscript()
            b.end()
            new_node = b.pop()
            for e in new_node.elts:
                e.typ_id = 'int'
        elif attr == 'strides':
            b.Tuple()
            b.Constant(0)
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('strides')
            b.Subscript()
            b.Constant(1)
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('strides')
            b.Subscript()
            b.end()
            new_node = b.pop()
            for e in new_node.elts:
                e.typ_id = 'int'
        elif attr == 'format':
            new_node = ast.Name('long', ctx=self._load)
        elif attr == 'pixels_address':
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('buf')
            new_node = b.pop()
        else:
            msg = f"Unknown Array2 attribute {attr}"
            raise BuildError(msg)
        new_node.typ_id = node.typ_id
        return new_node

    def Assign(self, node, symtab):
        # Only single assignment supported
        assert len(node.targets) == 1
        target = node.targets[0]
        value = node.value
        if target.typ_id != value.typ_id:
            typ_id_t = target.typ_id
            typ_id_v = value.typ_id
            msg = f"Mismatched assigned types: {typ_id_t} = {typ_id_v}"
            raise loops.BuildError(msg)
        return node

class ISurface:
    def __init__(self):
        self.build = astkit.TreeBuilder()
        self._load = ast.Load()
        self._store = ast.Store()

    def Name(self, node, symtab):
        return node

    def Call(self, node, symtab):
        # Assume class call
        return node.args[0]

    def Attribute(self, node, symtab):
        assert isinstance(node.ctx, ast.Load)
        attr = node.attr
        b = self.build
        if attr == 'shape':
            b.Tuple()
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('w')
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('h')
            b.end()
            new_node = b.pop()
            for e in new_node.elts:
                e.typ_id = 'int'
        elif attr == 'strides':
            b.Tuple()
            b.Constant(0)
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('format')
            b.Subscript()
            b.Attribute('BytesPerPixel')
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('pitch')
            b.end()
            new_node = b.pop()
            for e in new_node.elts:
                e.typ_id = 'int'
        elif attr == 'format':
            new_node = ast.Name('long', ctx=self._load)
        elif attr == 'pixels_address':
            b.Constant(0)
            b.push(node.value)
            b.Subscript()
            b.Attribute('pixels')
            new_node = b.pop()
        else:
            msg = f"Unknown Surface attribute {attr}"
            raise BuildError(msg)
        new_node.typ_id = node.typ_id
        return new_node

    def Assign(self, node, symtab):
        # Only single assignment supported
        assert len(node.targets) == 1
        target = node.targets[0]
        value = node.value
        if target.typ_id != value.typ_id:
            typ_id_t = target.typ_id
            typ_id_v = value.typ_id
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
        assert node.typ_id.startswith("loops.Pointer[")
        assert len(node.args) == 1
        value = node.args[0]
        value.typ_id = self.python_type
        if isinstance(value, ast.Name):
            self.symtab[value.id] = value.typ_id
        return value

    def BinOp(self, node, symtab):
        # Assuming <pointer> op <int> arithmetic only
        assert node.typ_id.startswith("loops.Pointer[")
        op = node.op
        if not isinstance(op, (ast.Add, ast.Sub)):
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
        assert node.value.typ_id.startswith('loops.Pointer[')
        for t in node.targets:
            if t.typ_id.startswith('loops.Pointer['):
                t.typ_id = self.python_type
        return node

    def AugAssign(self, node, symtab):
        # <pointer> op= <int> arithmetic only
        assert node.value.typ_id == 'int'
        op = node.op
        target = node.target
        if not isinstance(op, (ast.Add, ast.Sub)):
            op_name = type(op).__name__
            raise loops.BuildError(f"Unsupported op {op_name}")
        return node

class IPixel(IGeneric):
    """Pointer to C integer"""
    def __init__(self):
        super().__init__('loops.Pixel')
        self.build = astkit.TreeBuilder()

    def Name(self, node, symtab):
##        typ_id = as_c_type(node.typ_id)
##        node.typ_id = typ_id
        return node

    def Call(self, node, symtab):
        # Assume __init__ call
        assert node.typ_id.startswith('loops.Pixel[')
        replacement = node.args[0]
        replacement.typ_id = node.typ_id
        return replacement

    def Attribute(self, node, symtab):
        attr = node.attr
        if isinstance(node.ctx, ast.Load):
            if attr == 'pixel':
                return self.cast_int(node.value)
        else:
            if attr == 'pixel':
                # ((long*)<ptr>)[0]
                replacement = self.cast_int(node.value)
                replacement.ctx = ast.Store()
                return replacement
        msg = f"Unknown attribute {attr}"
        raise loops.BuildError(msg)

    def cast_int(self, node):
        # CAST('long*')(<ptr>)[0]
        c_type = as_c_type(node.typ_id)
        b = self.build
        b.Constant(0)
        b.Name('CAST')
        b.Call()
        b.Constant(c_type)
        b.end()
        b.Call()
        b.push(node)
        b.end()
        b.Subscript()
        replacement = b.pop()
        replacement.typ_id = c_type[:-1]
        return replacement

    def Assign(self, node, symtab):
        assert node.value.typ_id.startswith('loops.Pixel[')
        assert len(node.targets) == 1
        if node.targets[0].typ_id == 'long':
            node.value = self.cast_int(node.value)
        else:
            assert node.targets[0].typ_id == node.value.typ_id
        return node

class ITuple(IGeneric):
    def __init__(self):
        self.build = astkit.TreeBuilder()

    def Assign(self, node, symtab):
        assert node.value.typ_id.startswith('(')
        assert len(node.targets) == 1
        target = node.targets[0]
        value = node.value
        assert target.typ_id == value.typ_id
        b = self.build
        for t, v in zip(target.elts, value.elts):
            assert t.typ_id == v.typ_id
            b.push(v)
            b.push(t)
            b.Assign1()
        return b.pop_list()

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
    'loops.Tuple': ITuple(),
    }

class Inliner(IAny, ast.NodeTransformer):
    def __init__(self, symbol_table):
        super().__init__()
        self.symtab = symbol_table

    def lookup(self, node):
        typ_id = node.typ_id
        if typ_id.startswith('('):
            itype = self.symtab['loops.Tuple']
        else:
            try:
                itype = self.symtab[typ_id.partition('[')[0]]
            except KeyError:
                itype = None
        if itype is None:
            itype = i_any
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

##class ImportCollector(ast.NodeVisitor):
##    """Collect modules that need importing
##
##    Constructed names will be fully qualified names.
##    """
##    def __init__(self):
##        super().__init__()
##        self.imports = set()
##
##    def visit_Name(self, node):
##        elements = node.id.split('.')
##        if len(elements) > 1:
##            self.imports.add('.'.join(elements[0:-1]))

regex = re.compile(
r'[a-zA-Z_][a-zA-Z0-9_]+\.([a-zA-Z_][a-zA-Z0-9_]+)\[ctypes\.c_([a-z]+)\]')

translation = {'int': 'long', 'str': 'char*', 'float': 'double',
               'loops.Surface': 'SDL_Surface*', 'loops.Array2': 'Py_buffer*',
               'loops.Pixel': 'loops.Pixel'}

def as_c_type(typ_id):
    m = regex.match(typ_id)
    if m is None:
        return translation[typ_id]
    root, subtype = m.groups()
    if root == 'Pointer':
        return f'{sybtype}*'
    if root == 'Pixel':
        return f'{subtype}*'
    raise loops.BuildError(f"Untranslatable type {typ_id}")
