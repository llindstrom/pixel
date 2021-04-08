"""Compile loop descriptions file into a Python module

Need to separate out global and local symbol tables to support multiple
module level function declarations.

Get rid of 'arg_1 = argument_1' etc.
"""

import blitkit
import astkit
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
    symtab.update(typer_symbols)
    return module_ast, typer(module_ast, symtab)

def stage_2(module_ast):
    # Stage Two: Python code
    inline_types(module_ast, inliner_symbols)
    add_imports(module_ast)
    return ast.unparse(module_ast)

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

    visitor = Typer(symtab)
    visitor.visit(module)
    return visitor.symtab

def inline_types(module, symtab):
    """Replace types with inlined code"""

    visitor = Inliner(symtab)
    visitor.visit(module)

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

def evaluate(node, symtab):
    """eval a simple ast expression"""

    if isinstance(node, ast.Name):
        # Get value
        try:
            return symtab[node.id]
        except KeyError:
            msg = "Name {node.id} not in symbol table"
            raise blitkit.BuildError(msg)
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
        raise blitkit.BuildError(msg)

# Typer types
class Template:
    def __init__(self, full_name):
        self.full_name = full_name

    def __str__(self):
        return self.full_name

    def __eq__(self, other):
        return (str(other) == self.full_name or
                str(other) == 'expand.Any')

class TExternal(Template):
    def __repr__(self):
        return f"<TExternal({self!s})>"

class TAny(Template):
    def __init__(self):
        self.full_name = 'expand.Any'

    def __repr__(self):
        return "<TAny()>"

    def getattr(self, name):
        return self

    def getitem(self, key):
        return self

class Tstr(Template):
    """Python str"""
    def __init__(self):
        super().__init__('str')

    def __repr__(self):
        return "<Tstr()>"

class Tint(Template):
    """Python int"""
    def __init__(self):
        super().__init__('int')

    def __repr__(self):
        return "<Tint()>"

    def add(self, other):
        if not other == self:
            msg = "+: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

    def iadd(self, other):
        if not other == self:
            msg = "+: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)

    def sub(self, other):
        if not other == self:
            msg = "-: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

    def mult(self, other):
        if not other == self:
            msg = "*: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

    def lshift(self, other):
        if not other == self:
            msg = "<<: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

    def rshift(self, other):
        if not other == self:
            msg = ">>: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

    def mul(self, other):
        if not other == self:
            msg = "*: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

    def floordiv(self, other):
        if not other == self:
            msg = "//: incompatible type {}".format(other)
            raise blitkit.BuildError(msg)
        return self

class TGeneric(Template):
    def __init__(self, cls):
        super().__init__(f'blitkit.{cls.__name__[1:]}')
        self.cls = cls
        self._cache = {}

    def __repr__(self):
        return f"<{self.cls.__name__}[]>"

    def __getitem__(self, item_type):
        try:
            return self._cache[str(item_type)]
        except KeyError:
            if isinstance(item_type, tuple):
                t = self.cls(item_type)
            else:
                t = self.cls((item_type,))
            self._cache[str(item_type)] = t
        return t

    def __contains__(self, other):
        return isinstance(other, (self.cls, TAny))

    def getitem(self, arg):
        if arg in TTuple:
            item_typ_ids = tuple(arg)
            return self[item_typ_ids]
        return self[str(arg)]

@TGeneric
class TTuple(Template):
    def __init__(self, items):
        typ_ids = [str(item) for item in items]
        if len(typ_ids) == 1:
            full_name = f'({items[0]!s},)'
        else:
            typ_ids = [str(item) for item in items]
            full_name = f'({", ".join(typ_ids)})'
        super().__init__(full_name)
        self.items = typ_ids

    def __repr__(self):
        if len(self.items) == 0:
            return "<TTuple[()]>"
        strs = [f"'{typ_id}'" for typ_id in self.items]
        return f"<TTuple[{', '.join(strs)}]>"

    def getitem(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

@TGeneric
class TFunction(Template):
    def __init__(self, signature):
        rettype, *argtypes = signature
        super().__init__(f'({", ".join(argtypes)}) -> {rettype}')
        self.rettype = rettype
        self.argtypes = argtypes

    def __repr__(self):
        strs = [f"'{self.rettype}'"]
        strs.extend(f"'{typ_id}'" for typ_id in self.argtypes)
        return f"<TFunction[{', '.join(strs)}]>"

    def call(self, args):
        argtypes = self.argtypes
        if len(args) != len(argtypes):
            msg = f"function takes {len(argtypes)} args: got {len(args)}"
            raise blitkit.BuildError(msg)
        return self.rettype

@TGeneric
class TPointer(Template):
    def __init__(self, item_name):
        self.instance = TPointerInstance(item_name)
        super().__init__(f'(int) -> {self.instance!s}')

    def __repr__(self):
        return f"<Class {self.instance!r}>"

    def call(self, args):
        if len(args) != 1:
            msg = f"{self!r} accepts 1 argument: {len(args)} given"
            raise blitkit.BuildError(msg)
        if args[0] != Tint():
            msg = f"{self!r} argument 1 not an integer"
        return self.instance

class TPointerInstance(Template):
    def __init__(self, item_name):
        super().__init__(f'blitkit.Pointer[{item_name[0]}]')
        self.item = item_name[0]
        self.ttype_int = Tint()

    def __repr__(self):
        return f"<{type(self).__name__}[{self.item}]>"

    def add(self, other):
        if not other == self.ttype_int:
            msg = f"+: incompatible type {name}"
            raise blitkit.BuildError(msg)
        return self

    def iadd(self, other):
        if not other == self.ttype_int:
            msg = f"+: incompatible type {other}"
            raise blitkit.BuildError(msg)

    def sub(self, other):
        if not other == self.ttype_int:
            msg = f"-: incompatible type {name}"
            raise blitkit.BuildError(msg)
        return self

@TGeneric
class TPixel(Template):
    def __init__(self, item_name):
        self.instance = TPixelInstance(item_name)
        super().__init__(f'(blitkit.Pointer[Any]) -> {self.instance!s}')

    def __repr__(self):
        return f"<Class {self.instance!r}>"

    def call(self, args):
        if len(args) != 1:
            msg = f"{self!r} accepts 1 arguments: {len(args)} given"
            raise blitkit.BuildError(msg)
        if not isinstance(args[0], TPointerInstance):
            msg = f"{self!r} argument 1 not a pointer"
        return self.instance

class TPixelInstance(Template):
    def __init__(self, item_name):
        super().__init__(f'blitkit.Pixel[{item_name[0]}]')
        self.item = item_name[0]

    def __repr__(self):
        return f"<{type(self).__name__}[{self.item}]>"

    def getattr(self, name):
        if name == 'pixel':
            return Tint()
        raise blitkit.BuildError(f"Invalid attribute {name}")

    def setattr(self, name, value):
        if name == 'pixel':
            if not (value == self or value == Tint()):
                raise blitkit.BuildError("attribute/value mismatch")
        else:
            raise blitkit.BuildError(f"Invalid attribute {name}")

class TPixels(Template):
    def getattr(self, attr):
        if attr == 'pixels_address':
            return Tint()
        if attr == 'shape':
            return TTuple['int', 'int']
        if attr == 'strides':
            return TTuple['int', 'int']
        if attr == 'format':
            return TExternal('ctypes.c_long')
        raise blitkit.BuildError(f"Unknown attribute {attr}")

class TArray2(TPixels):
    def __init__(self):
        super().__init__('blitkit.Array2')

    def call(self, args):
        # Assume class call
        assert(len(args) == 1)
        assert(str(args[0]) == str(self))
        return self

class TSurface(TPixels):
    def __init__(self):
        super().__init__('blitkit.Surface')

    def call(self, args):
        # Assume class call
        assert(len(args) == 1)
        assert(str(args[0]) == str(self))
        return self

typer_symbols = {
    'int': Tint(),
    'str': Tstr(),
    'tuple': TTuple,
    'blitkit.Pixel': TPixel,
    'blitkit.Pointer': TPointer,
    'blitkit.Array2': TArray2(),
    'blitkit.Surface': TSurface(),
    'ctypes.c_char': TExternal('ctypes.c_char'),
    'ctypes.c_long': TExternal('ctypes.c_long'),
    }

class Typer(ast.NodeVisitor):
    def __init__(self, symbol_table):
        super().__init__()
        self.symtab = symbol_table.copy()

    def lookup(self, symbol):
        try:
            ttype = self.symtab[symbol]
        except KeyError:
            ttype = None
        if ttype is None:
            raise blitkit.BuildError(f"Unknown symbol {symbol}")
        if isinstance(ttype, str):
            return self.lookup(ttype)
        return ttype

    def visit_Module(self, node):
        for child in node.body:
            if isinstance(child, ast.ImportFrom):
                print("Have some symbol definitions")
            elif isinstance(child, ast.If):
                print("Have a compile-time conditional statement")
            elif isinstance(child, ast.FunctionDef):
                self.visit(child)
            else:
                msg = f"Unknown module level statement {child}"
                raise blitkit.BuildError(msg)

    def visit_FunctionDef(self, node):
        for a in node.args.args:
            typ_id = a.annotation.value
            ttype = self.lookup(typ_id)
            self.symtab[a.arg] = typ_id 
            self.symtab[str(ttype)] = ttype
        self.generic_visit(node)

    def visit_Assign(self, node):
        value = node.value
        self.visit(value)
        typ_id = value.typ_id
        for target in node.targets:
            target.typ_id = typ_id
            self.visit(target)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        op = node.op
        ttype_t = self.lookup(node.target.typ_id)
        ttype_v = self.lookup(node.value.typ_id)
        if isinstance(op, ast.Add):
            ttype_t.iadd(ttype_v)
        elif isinstance(op, ast.Sub):
            ttype_t.isub(ttype_v)
        elif isinstance(op, ast.Mult):
            ttype_t.imult(ttype_v)
        elif isinstance(op, ast.FloorDiv):
            ttype_t.ifloordiv(ttype_v)
        elif isinstance(op, ast.LShift):
            ttype_t.ilshift(ttype_v)
        elif isinstance(op, ast.RShift):
            ttype_t.irshift(ttype_v)
        else:
            op_name = type(op).__name__
            raise blitkit.BuildError(f"Unsupported op {op_name}")

    def visit_BinOp(self, node):
        op = node.op
        self.generic_visit(node)
        ttype_l = self.lookup(node.left.typ_id)
        ttype_r = self.lookup(node.right.typ_id)
        if isinstance(op, ast.Add):
            ttype_op = ttype_l.add(ttype_r)
        elif isinstance(op, ast.Sub):
            ttype_op = ttype_l.sub(ttype_r)
        elif isinstance(op, ast.Mult):
            ttype_op = ttype_l.mult(ttype_r)
        elif isinstance(op, ast.FloorDiv):
            ttype_op = ttype_l.floordiv(ttype_r)
        elif isinstance(op, ast.LShift):
            ttype_op = ttype_l.lshift(ttype_r)
        elif isinstance(op, ast.RShift):
            ttype_op = ttype_l.rshift(ttype_r)
        else:
            op_name = type(op).__name__
            raise blitkit.BuildError(f"Unsupported op {op_name}")
        node.typ_id = str(ttype_op)
        self.symtab[node.typ_id] = ttype_op

    def visit_Call(self, node):
        self.generic_visit(node)
        typ_id_f = node.func.typ_id
        args = [self.lookup(a.typ_id) for a in node.args]
        ttype = self.lookup(typ_id_f).call(args)
        node.typ_id = str(ttype)
        self.symtab[node.typ_id] = ttype

    def visit_Constant(self, node):
        value = node.value
        if isinstance(value, int):
            node.typ_id = 'int'
        elif isinstance(value, str):
            node.typ_id = 'str'
        else:
            msg = f"Unknown literal {value}"
            raise blitkit.BuildError(msg)

    def visit_Name(self, node):
        name = node.id
        if isinstance(node.ctx, ast.Load):
            ttype = self.lookup(name)
            node.typ_id = str(ttype)
        else:
            try:
                ttype = self.lookup(name)
            except blitkit.BuildError:
                self.symtab[name] = node.typ_id
            else:
                try:
                    typ_id = node.typ_id
                except AttributeError:
                    node.typ_id = str(ttype)
                else:
                    ttype_a = self.lookup(node.typ_id)
                    if ttype_a != ttype:
                        msg = (f"Name {name} has type {ttype} "
                                "but is assigned a {ttype_a}")
                        raise blitkit.BuildError(msg)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        loading = isinstance(node.ctx, ast.Load)
        typ_id = get_typ_id(node.value)
        if typ_id is None:
            context = "Getting" if loading else "Setting"
            msg = f"{context} attribute of untyped value"
            raise blitkit.BuildError(msg)
        ttype_v = self.lookup(typ_id)
        typ_id = get_typ_id(node)
        if typ_id is None:
            ttype = ttype_v.getattr(node.attr)
            node.typ_id = str(ttype)
            self.symtab[node.typ_id] = ttype
        else:
            ttype_a = self.lookup(typ_id)
            ttype_v.setattr(node.attr, ttype_a)

    def visit_Subscript(self, node):
        self.generic_visit(node)
        loading = isinstance(node.ctx, ast.Load)
        typ_id = get_typ_id(node.value)
        if typ_id is None:
            context = "Getting" if loading else "Setting"
            msg = f"{context} subscript of untyped value"
            raise blitkit.BuildError(msg)
        ttype_v = self.lookup(typ_id)
        typ_id = get_typ_id(node.slice)
        if typ_id is None:
            context = "Accessing attribute with unptyped key"
            raise blitkit.BuildError(msg)
        ttype_k = self.lookup(typ_id)
        typ_id = get_typ_id(node)
        if typ_id is None:
            ttype = ttype_v.getitem(ttype_k)
            node.typ_id = str(ttype)
            self.symtab[node.typ_id] = ttype
        else:
            ttype_a = self.lookup(typ_id)
            ttype_t.setitem(node.attr, ttype_k, ttype_a)

    def visit_Tuple(self, node):
        if isinstance(node.ctx, ast.Load):
            self.generic_visit(node)
            elem_typ_ids = [n.typ_id for n in node.elts]
            ttype = TTuple[tuple(elem_typ_ids)]
            typ_id = str(ttype)
            node.typ_id = typ_id
            self.symtab[typ_id] = ttype
        else:
            ttype_a = self.lookup(get_typ_id(node))
            if ttype_a not in TTuple:
                msg = f"Assigning a {ttype} to a tuple"
                raise blitkit.BuildError(msg)
            if len(ttype_a) != len(node.elts):
                msg = (f"Assigning a {len(ttype_a)} tuple"
                       f" to a {len(node.elts)} tuple")
                raise blitkit.BuildError(msg)
            for element, typ_id in zip(node.elts, ttype_a):
                element.typ_id = typ_id
                self.visit(element)

def get_typ_id(node):
    try:
        return node.typ_id
    except AttributeError:
        return None

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
        blitkit_typ_id = f"{self.root_name}[{tmpl_arg}]"
        try:
            inliner = symtab[typ_id]
        except KeyError:
            symtab[typ_id] = self
            symtab[blitkit_typ_id] = typ_id
        return ast.Name(blitkit_typ_id, ctx=node.ctx, typ_id=blitkit_typ_id)

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
            raise blitkit.BuildError(msg)
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
            b.End()
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
            raise blitkit.BuildError(msg)
        return node

class IPointer(IGeneric):
    python_type = 'int'

    def __init__(self):
        super().__init__("blitkit.Pointer")

    def Name(self, node, symtab):
        if self.subtype(node.typ_id) is not None:
            node.typ_id = self.python_type
            symtab[node.id] = node.typ_id
        return node

    def Call(self, node, symtab):
        # Assume __init__ call
        assert(node.typ_id.startswith("blitkit.Pointer["))
        assert(len(node.args) == 1)
        value = node.args[0]
        value.typ_id = self.python_type
        if isinstance(value, ast.Name):
            self.symtab[value.id] = value.typ_id
        return value

    def BinOp(self, node, symtab):
        # Assuming <pointer> op <int> arithmetic only
        assert(node.typ_id.startswith("blitkit.Pointer["))
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
            raise blitkit.BuildError(f"Unsupported op {op_name}")
        return node

    def Compare(self, node, symtab):
        if node.left.typ_id.startswith('blitkit.Pointer['):
            node.left.typ_id = self.python_type
        for other in node.comparators:
            if other.typ_id.startswith('blitkit.Pointer['):
                other.typ_id = self.python_type
        return node

    def Assign(self, node, symtab):
        # value is a pointer
        assert(node.value.typ_id.startswith('blitkit.Pointer['))
        for t in node.targets:
            if t.typ_id.startswith('blitkit.Pointer['):
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
            raise blitkit.BuildError(f"Unsupported op {op_name}")
        return node

class IPixel(IGeneric):
    """Pointer to C integer"""
    def __init__(self):
        super().__init__('blitkit.Pixel')
        self.build = astkit.TreeBuilder()

    def Name(self, node, symtab):
        if self.subtype(node.typ_id) is not None:
            symtab[node.id] = node.typ_id
        return node

    def Call(self, node, symtab):
        # Assume __init__ call
        assert(node.typ_id.startswith('blitkit.Pixel['))
        replacement = node.args[0]
        replacement.typ_id = node.typ_id
        return replacement

    def Attribute(self, node, symtab):
        attr = node.attr
        if isinstance(node.ctx, ast.Load):
            if attr == 'pixel':
                return self.cast_int(self.value)
        else:
            if attr == 'pixel':
                # ctypes.c_<int>.from_address(<ptr>).value
                subtype = self.subtype(node.value.typ_id)
                assert(subtype is not None)
                b = self.build
                b.Name(subtype)
                b.Attribute('from_address')
                b.Call()
                b.push(node.value)
                b.end()
                b.Attribute('value')
                expr = b.pop()
                expr.ctx = ast.Store()
                expr.typ_id = 'int'
                return expr
        msg = f"Unknown attribute {attr}"
        raise blitkit.BuildError(msg)

    def cast_int(self, node):
        subtype = self.subtype(node.typ_id)
        b = self.build
        b.Name('int')
        b.Call()
        b.Name(subtype)
        b.Attribute('from_address')
        b.Call()
        b.push(node)
        b.end()
        b.Attribute('value')
        b.end()
        return b.pop()

    def Assign(self, node, symtab):
        assert(node.value.typ_id.startswith('blitkit.Pixel['))
        assert(len(node.targets) == 1)
        assert(node.targets[0].typ_id == 'int')
        node.value = self.cast_int(node.value)
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
    'blitkit.Array2': IArray2(),
    'blitkit.Surface': ISurface(),
    'blitkit.Pointer': IPointer(),
    'blitkit.Pixel': IPixel(),
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

# This is what should be generated by expand.expand for
#
#     @blitkit.blitter(blitkit.Array2, blitkit.Surface)
#     def do_blit(s, d):
#         d.pixel = s
#     
# Function globals are: 'ctypes'
#
import ctypes

def do_blit(arg_1: 'bitkit.Array2', arg_2: 'blitkit.Surface'):
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
