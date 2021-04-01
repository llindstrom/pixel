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
    symtab.update(inliner_symbols)
    inline_types(module_ast, symtab)
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

    ## STUB: does nothing
    return symtab

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

class TAny(Template):
    def __init__(self):
        self.full_name = 'expand.Any'

    def getattr(self, name):
        return self

    def getitem(self, key):
        return self

class Tint(Template):
    """Python int"""
    def __init__(self):
        super().__init__('int')

    def add(self, other):
        if not other == self:
            msg = "+: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def sub(self, other):
        if not other == self:
            msg = "-: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def lshift(self, other):
        if not other == self:
            msg = "<<: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def rshift(self, other):
        if not other == self:
            msg = ">>: incompatible type {}".format(other)
            raise CompileError(msg)
        return self
    
    def mul(self, other):
        if not other == self:
            msg = "*: incompatible type {}".format(other)
            raise CompileError(msg)
        return self
    
    def floordiv(self, other):
        if not other == self:
            msg = "//: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

class TGeneric:
    def __init__(self, cls):
        self.cls = cls
        self._cache = {}

    def __getitem__(self, item_type):
        try:
            return self._cache[item_type]
        except KeyError:
            t = self.cls(item_type)
            self._cache[item_type] = t
        return t

@TGeneric
class TTuple(Template):
    def __init__(self, item_names):
        if len(item_names) == 1:
            full_name = f'({item_names[0]},)'
        else:
            full_name = f'({", ".join(item_names)})'
        super().__init__(full_name)
        self.items = item_names

    def getitem(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

@TGeneric
class TFunction(Template):
    def __init__(self, signature):
        super().__init__(f'({", ".join(signature[1:])}) -> {signature[0]}')
        self.rettype = signature[0]
        self.argtypes = signature[1:]

    def call(self, args):
        argtypes = self.argtypes
        if len(args) != len(argtypes):
            msg = f"function takes {len(argtypes)} args: got {len(args)}"
            raise blitkit.BuildError(msg)
        return self.restype

@TGeneric
class TPointer(Template):
    def __init__(self, item_name):
        super().__init__(f'blitkit.Pointer[{item_name}]')

    def add(self, other):
        if not other == self:
            msg = "+: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def sub(self, other):
        if not other == self:
            msg = "-: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def lshift(self, other):
        if not other == self:
            msg = "<<: incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def rshift(self, other):
        if not other == self:
            msg = ">>: incompatible type {}".format(other)
            raise CompileError(msg)
        return self
    
    def mul(self, other):
        if not other == self:
            msg = "*: incompatible type {}".format(other)
            raise CompileError(msg)
        return self
    
    def floordiv(self, other):
        if not other == self:
            msg = "//: incompatible type {}".format(other)
            raise CompileError(msg)
        return self
    
@TGeneric
class TPixel(Template):
    def __init__(self, item_name):
        super().__init__(f'blitkit.Pixel[{item_name}]')

    def getattr(self, name):
        if name == 'pixel':
            return Tint()
        raise CompileError("Invalid attribute {}".format(name))

    def setattr(self, name, value):
        if name == 'pixel':
            if not (value == self or value == Tint()):
                raise CompileError("attribute/value mismatch")
        else:
            raise blitkit.BuildError(f"Invalid attribute {name}")

class TArray2(Template):
    def __init__(self):
        super().__init__('blitkit.Array2')

    def getattr(self, attr):
        if attr == 'shape':
            return TTuple['int', 'int']
        if attr == 'strides':
            return TTuple['int', 'int']
        if attr == '__array__interface__':
            return TAny()
        raise blitkit.BuildError(f"Unknown attribute {attr}")

class TSurface(Template):
    def __init__(self):
        super().__init__('blitkit.Surface')

    def getattr(self, attr):
        if attr == '_pixels_address':
            return Tint()
        if attr == '_get_bytesize':
            return TFunction('int')
        if attr == '_get_pitch':
            return TFunction('int')
        raise blitkit.BuildError(f"Unknown attribute {attr}")

typer_symbols = {
    'int': Tint(),
    'tuple': TTuple,
    'blitkit.Pixel': TPixel,
    'blitkit.Pointer': TPointer,
    'blitkit.Array2': TArray2(),
    'blitkit.Surface':  TSurface(),
    }

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
        raise BuildError(msg)

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

class Typer(ast.NodeVisitor):
    def __init__(self, symbol_table):
        self.symtab = symbol_table.copy()

    def lookup(symbol):
        try:
            ttype = self.symtab[symbol]
        except:
            raise blitkit.BuildError("Unknown symbol {symbol}")
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
                raise CompilerError("Unknown top level statement")

    def visit_FunctionDef(self, node):
        symtab = self.symtab
        for a in node.args.args:
            ttype = self.lookup(a.annotation.value)
            self.symtab[a.arg] = str(ttype)
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.generic_visit(node)
        value = node.value
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.typ_id is None:
                    self.symtab[name] = target.typ_id = value.typ_id
                else:
                    ttype_v = self.lookup(value.typ_id)
                    ttype_t = self.lookup(target.typ_id)
                    if ttype_t != ttype_v:
                        t, v = str(ttype_t), str(ttype_v)
                        msg = f"Incompatible assignment types: {r} = {v}"
                        raise BuildError(msg)
            elif isinstance(target, ast.Attribute):
                ttype_t = self.lookup(target.value.typ_id)
                ttype_v = self.lookup(target.typ_id)
                ttype_t.setattr(target.attr, value.ttype)
            elif isinstance(target, ast.Subscript):
                ttype_t = self.lookup(target.value.typ_id)
                ttype_v = self.lookup(value.typ_id)
                ttype_k = self.lookup(target.slice.typ_id)
                ttype_t.setitem(ttype_k, ttype_v)
            else:
                msg = "{} assignment unsupported".format(type(t).__name__)

    def visit_BinOp(self, node):
        op = node.op
        self.generic_visit(node)
        ttype_l = self.lookup(node.left.typ_id)
        ttype_r = self.lookup(node.right.typ_id)
        if isinstance(op, ast.Add):
            node.typ_id = ttype_l.add(ttype_r)
        elif isinstance(op, ast.Sub):
            node.typ_id = ttype_l.sub(ttype_r)
            node.ttype = node.left.ttype.sub(node.right.ttype)
        elif isinstance(op, ast.Mult):
            node.typ_id = ttype_l.mult(ttype_r)
        elif isinstance(op, ast.FloorDiv):
            node.typ_id = ttype_l.floordiv(ttype_r)
        elif isinstance(op, ast.LShift):
            node.typ_id = ttype_l.lshift(ttype_r)
        elif isinstance(op, ast.RShift):
            node.typ_id = ttype_l.rshift(ttype_r)
        else:
            raise CompilerError("Unsupported op {}".format(type(op).__name__))
        
    def visit_Attribute(self, node):
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            typ_id = node.value.typ_id
            if typ_id is None:
                raise blitkit.BuildError("Getting attribute on an undefined symbol")
            ttype_v = self.lookup(node.value.typ_id)
            node.typ_id = ttype_v.getattr(node.attr)

    def visit_Name(self, node):
        try:
            node.typ_id = self.symtab[node.id]
        except KeyError:
            node.typ_id = None

    def visit_Constant(self, node):
        value = node.value
        if isinstance(value, int):
            node.typ_id = 'int'
        else:
            msg = f"Unknown literal {value}"
            raise blitkit.BuildError(msg)

###  <==================== Up to here
    def visit_Call(self, node):
        func_id = node.func.id
        args = []
        self.generic_visit(node)
        for a in node.args:
            args.append(a.ttype)
        try:
            node.ttype = self.symtab[func_id].call(*args)
        except KeyError:
            raise blitkit.BuildError("Unknown function {}".format(func_id))

    def visit_Tuple(self, node):
        pass ### Do tuple stuff

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
