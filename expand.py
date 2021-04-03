"""Compile loop descriptions file into a Python module
"""

import blitkit
import ast

def expand(source, path, symbol_table):
    """expand(source: str, path: string, glbs: dict) -> str
    """

    symtab = symbol_table.copy()
    # Stage One: General template
    module_ast = ast.parse(source, path, 'exec')
    inline_decorators(module_ast, symtab)

    # Stage Two: Specialize template
    symtab.update(typer_symbols)
    typer(module_ast, symtab)
##    symtab.update(inliner_symbols)
##    inline_types(module_ast, symtab)
    add_imports(module_ast)
    return ast.unparse(module_ast), symtab

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

def inline_types(module, symtab):
    """Replace types with inlined code"""

    ## STUB: does nothing
    return module, symtab

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
        super().__init__(f'generic.{cls.__name__}')
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
class TPointerClass(Template):
    def __init__(self, item_name):
        self.instance = TPointer(item_name)
        super().__init__(f'class.{self.instance!s}')

    def __repr__(self):
        return f"<Class {self.instance!r}>"

    def call(self, args):
        if len(args) != 2:
            msg = f"{self!r} accepts 2 arguments: {len(args)} given"
            raise blitkit.BuildError(msg)
        if args[1] != Tint():
            msg = f"{self!r} argument 2 not an integer"
        return self.instance

class TPointer(Template):
    def __init__(self, item_name):
        super().__init__(f'blitkit.Pointer[{item_name[0]}]')
        self.item = item_name[0]
        self.ttype_int = Tint()

    def __repr__(self):
        return f"<TPointer[{self.item}]>"

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
class TPixelClass(Template):
    def __init__(self, item_name):
        self.instance = TPixel(item_name)
        super().__init__(f'class.{self.instance!s}')

    def __repr__(self):
        return f"<Class {self.instance!r}>"

    def call(self, args):
        if len(args) != 1:
            msg = f"{self!r} accepts 1 arguments: {len(args)} given"
            raise blitkit.BuildError(msg)
        if not isinstance(args[0], TPointer):
            msg = f"{self!r} argument 1 not a pointer"
        return self.instance

class TPixel(Template):
    def __init__(self, item_name):
        super().__init__(f'blitkit.Pixel[{item_name[0]}]')
        self.item = item_name[0]

    def __repr__(self):
        return f"<TPixel[{self.item}]>"

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

class TArray2(Template):
    def __init__(self):
        super().__init__('blitkit.Array2')

    def __repr__(self):
        return "<TArray2['numpy.int32']>"

    def getattr(self, attr):
        if attr == 'shape':
            return TTuple['int', 'int']
        if attr == 'strides':
            return TTuple['int', 'int']
        if attr == '__array_interface__':
            return TAny()
        raise blitkit.BuildError(f"Unknown attribute {attr}")

class TSurface(Template):
    def __init__(self):
        super().__init__('blitkit.Surface')

    def __repr__(self):
        return "<TSurface>[32]"

    def getattr(self, attr):
        if attr == '_pixels_address':
            return Tint()
        if attr == 'get_bytesize':
            return TFunction('int')
        if attr == 'get_pitch':
            return TFunction('int')
        raise blitkit.BuildError(f"Unknown attribute {attr}")

typer_symbols = {
    'int': Tint(),
    'str': Tstr(),
    'tuple': 'generic.TTuple',
    'generic.TTuple': TTuple,
    'blitkit.Pixel': 'generic.TPixelClass',
    'generic.TPixelClass': TPixelClass,
    'blitkit.Pointer': 'generic.TPointerClass',
    'generic.TPointerClass': TPointerClass,
    'blitkit.Array2': 'generic.TArray2',
    'generic.TArray2': TArray2(),
    'blitkit.Surface': 'generic.TSurface',
    'generic.TSurface': TSurface(),
    'ctypes.c_char': TExternal('ctypes.c_char'),
    'ctypes.c_long': TExternal('ctypes.c_char'),
    }

class Typer(ast.NodeVisitor):
    def __init__(self, symbol_table):
        self.symtab = symbol_table

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
            ttype = self.lookup(a.annotation.value)
            self.symtab[a.arg] = str(ttype)
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
class IPointer:
    python_type = int

    def __init__(self, ctype_name):
        ctype = eval(ctype_name)
        self.size = ctypes.sizeof(ctype)

    def new(self, args):
        if len(args) != 2:
            raise blitkit.BuildError("Pointer class expects 2 arguments")
        return args[1]

    def int(self, node):
        return node

    def visit_Add(self, node):
        if self.size > 1:
            node.right = ast.Mult(node.right, Constant(self.size))
        return node

    def visit_IAdd(self, node):
        if self.size > 1:
            node.value = ast.Mult(node.value, Constant(self.size))
        return node

    def visit_BinOp(self, node):
        pass

    def Lt(self, node):
        return node

class IPixel:
    """Pointer to C long"""
    def __init__(self, ctype_name):
        self.build = astkit.TreeBuilder()
        self.python_type = eval(ctype_name)

    def Attribute(self, node):
        attr = node.attr
        if isinstance(node.ctx, ast.Load):
            if attr == 'pixel':
                return self.cast_int(node.value)
        else:
            if attr == 'pixel':
                b = self.build
                b.Name('ctypes')
                b.Attribute('c_long')
                b.Attritute('from_address')
                b.Call()
                b.push(node)
                b.end
                b.Attribute('value')
                return b.pop()
        msg = f"Unknown attribute {attr}"
        raise blitkit.BuildError(msg)

    def int(self, node):
        return self.cast_int(node.args.args[0].arg)

    def cast_int(self, node):
        b = self.build
        b.Name('int')
        b.Call()
        b.Name('ctypes')
        b.Attribute('c_long')
        b.Attritute('from_address')
        b.Call()
        b.push(node)
        b.end
        b.Attribute('value')
        b.end()
        return b.pop()

inliner_symbols = {
    'blitkit.Pointer': IPointer,
    'blitkit.Pixel': IPixel,
    }

class ImportCollector(ast.NodeVisitor):
    """Collect modules that need importing

    Constructed names will be fully qualified names.
    """
    def __init__(self):
        self.imports = set()

    def visit_Name(self, node):
        elements = node.id.split('.')
        if len(elements) > 1:
            self.imports.add('.'.join(elements[0:-1]))
