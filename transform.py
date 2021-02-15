"""Test the transformation of a template language ast into a low level ast.

In this case the template and target languages are prototyped as Python 3.9.

For Python 3.5 and later.
"""

import ast

class CompileError(Exception):
    pass

class TNoneType:
    """None has no useable type: For error detection.

    Constant 'None' is reserved for the undefined TemplateType type.
    This class represents its atual ttype.
    """
    def __init__(self):
        pass

    def __eq__(self, other):
        return False

    def __str__(self):
        return "TNoneType"

class Cast:
    # To add when TInt takes bit sizes
    pass

class TInt:
    # Update TInt to take a bit size argument?
    def __init__(self):
        pass

    def __eq__(self, other):
        return type(other) is type(self)

    def __str__(self):
        return "TInt"

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
    
class TGroup:
    def __init__(self, base_type, size):
        self.base_type = base_type
        self.size = size

    def __str__(self):
        return "TGroup({}, {})".format(self.base_type, self.size)

    # Update these operators to call base_type operations
    def add(self, other):
        if not (other == self.base_type or self == other):
            msg = "+: Incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def sub(self, other):
        if not (other == self.base_type or self == other):
            msg = "-: Incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def rshift(self, other):
        if not (other == self.base_type or self == other):
            msg = ">>: Incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def lshift(self, other):
        if not (other == self.base_type or self == other):
            msg = "<<: Incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def mul(self, other):
        if not (other == self.base_type or self == other):
            msg = "*: Incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def floordiv(self, other):
        if not (other == self.base_type or self == other):
            msg = "//: Incompatible type {}".format(other)
            raise CompileError(msg)
        return self

    def __len__(self):
        return self.size

    def __eq__(self, other):
        return isinstance(other, type(self)) and len(other) == len(self)

class TPixel:
    def __init__(self, base_type):
        self.base_type = base_type

    def __str__(self):
        return "TPixel({})".format(self.base_type)

    def getattr(self, name):
        if not all(a in "rgba" for a in name):
            raise CompileError("Invalid attribute {}".format(name))
        if len(name) == 1:
            return self.base_type
        return TGroup(self.base_type, len(name))

    def setattr(self, name, value):
        if not all(a in "rgba" for a in name):
            raise CompileError("Invalid attribute {}".format(name))
        alen = len(name)
        if value == self.base_type:
            pass
        elif alen != len(value) or value.base_type != self.base_type:
            raise CompileError("attribute/value mismatch")

    def degroup_attr(self, name, posn):
        a = name[posn]
        if a not in 'rgba':
            raise CompilerError("Invalid attribute {}".format(a))
        return a, self.base_type

class TMin:
    wraps = 'min'
    def call(self, a, b):
        # inadiquate
        return a

class TAlphaBlendComp:
    wraps = 'ALPHA_BLEND_COMP'
    def call(self, a, b, c):
        # inadiquate
        return a

symtab = {
    'Pixel': TPixel(TInt()),
    'MIN': TMin(),
    'ALPHA_BLEND_COMP': TAlphaBlendComp(),
    'int': TInt()
    }

class Typer(ast.NodeVisitor):
    def __init__(self):
        self.symtab = symtab.copy()

    def visit_FunctionDef(self, node):
        symtab = self.symtab
        for a in node.args.args:
            ttype_name = a.annotation.id
            try:
                ttype = symtab[ttype_name]
            except KeyError:
                raise CompilerError("Unknown ttype {}".format(ttype_name))
            self.symtab[a.arg] = ttype
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.generic_visit(node)
        value = node.value
        for t in node.targets:
            if isinstance(t, ast.Name):
                id = t.id
                if t.ttype is None:
                    self.symtab[id] = t.ttype = value.ttype 
                elif not (t.ttype == value.ttype):
                    msg = "Incompatible types: {} = {}".format(t.ttype, value)
                    raise CompileError(msg)
            elif isinstance(t, ast.Attribute):
                t.value.ttype.setattr(t.attr, value.ttype)
            else:
                msg = "{} assignment unsupported".format(type(t).__name__)

    def visit_BinOp(self, node):
        op = node.op
        self.generic_visit(node)
        if isinstance(op, ast.Add):
            node.ttype = node.left.ttype.add(node.right.ttype)
        elif isinstance(op, ast.Sub):
            node.ttype = node.left.ttype.sub(node.right.ttype)
        elif isinstance(op, ast.Mult):
            node.ttype = node.left.ttype.mul(node.right.ttype)
        elif isinstance(op, ast.FloorDiv):
            node.ttype = node.left.ttype.floordiv(node.right.ttype)
        elif isinstance(op, ast.LShift):
            node.ttype = node.left.ttype.lshift(node.right.ttype)
        elif isinstance(op, ast.RShift):
            node.ttype = node.left.ttype.rshift(node.right.ttype)
        else:
            raise CompilerError("Unsupported op {}".format(type(op).__name__))
        
    def visit_Attribute(self, node):
        self.generic_visit(node)
        # Using 'getattr' for both Load and Store doesn't feel right.
        ttype = node.value.ttype
        if (ttype is None):
            raise CompileError("Retriving attribute of undefined symbol")
        node.ttype = ttype.getattr(node.attr)

    def visit_Name(self, node):
        id = node.id
        node.ttype = self.symtab.setdefault(id)

    def visit_Constant(self, node):
        value = node.value
        if isinstance(value, int):
            node.ttype = TInt()
        elif value is None:
            node.ttype = TNoneType()
        else:
            msg = "Unknown literal {}".format(value)
            raise CompileError(msg)

    def visit_Call(self, node):
        func_id = node.func.id
        args = []
        self.generic_visit(node)
        for a in node.args:
            args.append(a.ttype)
        try:
            node.ttype = self.symtab[func_id].call(*args)
        except KeyError:
            raise CompileError("Unknown function {}".format(func_id))

    # Python 3.7 and earlier
    def visit_Num(self, node):
        node.ttype = TInt()

    def _visit_unsupported_literal(self, node):
        msg = "{} literals not supported".format(type(node).__name__)
        raise CompilerError(msg)

    visit_Str = visit_Bytes = visit_Ellipsis = _visit_unsupported_literal

class Degrouper(ast.NodeTransformer):

    def __init__(self):
        self._temp_count = 0

    class Copier(ast.NodeVisitor):

        def __init__(self, strand):
            self.strand = strand

        def visit(self, node):
            new_node = ast.NodeTransformer.visit(self, node)
            if not hasattr(new_node, 'ttype'):
                try:
                    new_node.ttype = node.ttype
                except AttributeError:
                    pass
            return ast.copy_location(new_node, node)

        def visit_Assign(self, node):
            targets = [self.visit(t) for t in node.targets]
            value = self.visit(node.value)
            return ast.Assign(targets, value)

        def visit_Constant(self, node):
            return ast.Constant(node.value)

        def visit_Name(self, node):
            id = node.id
            ttype = node.ttype
            if isinstance(ttype, TGroup):
                # Unpack a Group
                id = '{}_{}'.format(id, self.strand)
                ttype = ttype.base_type
            ctx = self.visit(node.ctx)
            new_node = ast.Name(id, ctx)
            new_node.ttype = ttype
            return new_node

        def visit_Attribute(self, node):
            value = self.visit(node.value)
            ctx = self.visit(node.ctx)
            attr = node.attr
            ttype = node.ttype
            if isinstance(ttype, TGroup):
                attr, ttype = value.ttype.degroup_attr(attr, self.strand)
            new_node = ast.Attribute(value, attr, ctx)
            new_node.ttype = ttype
            return new_node

        def visit_Load(self, node):
            return ast.Load()

        def visit_Store(self, node):
            return ast.Store()

        def visit_Add(self, node):
            return ast.Add()

        def visit_Sub(self, node):
            return ast.Sub()

        def visit_Mult(self, node):
            return ast.Mult()

        def visit_FloorDiv(self, node):
            return ast.FloorDiv()

        def visit_LShift(self, node):
            return ast.LShift()

        def visit_RShift(self, node):
            return ast.RShift()

        def visit_BinOp(self, node):
            left = self.visit(node.left)
            op = self.visit(node.op)
            right = self.visit(node.right)
            new_node = ast.BinOp(left, op, right)
            ttype = node.ttype
            if isinstance(ttype, TGroup):
                ttype = ttype.base_type
            new_node.ttype = ttype
            return new_node

        def visit_Call(self, node):
            func = self.visit(node.func)
            if isinstance(func, ast.Name):
                try:
                    func.id = symtab[func.id].wraps
                except AttributeError:
                    pass
                except KeyError:
                    pass
            args = [self.visit(a) for a in node.args]
            new_node = ast.Call(func, args, [])
            ttype = node.ttype
            if isinstance(ttype, TGroup):
                ttype = ttype.base_type
            new_node.ttype = ttype
            return new_node
    
        # Python 3.7 and earlier
        def visit_Num(self, node):
            return ast.Num(node.n) 

    def visit_Assign(self, node):
        targets = node.targets
        ttype = targets[0].ttype
        if isinstance(ttype, TGroup):
            if len(targets) > 1:
                raise CompileError("Multitarget assignment unsupported")
            size = len(ttype)
            assigns = [self.Copier(i).visit(node) for i in range(size)]
            assigns += self._resolve_overwrites(assigns)
            return assigns
        return node

    def _resolve_overwrites(self, assigns):
        extras = []
        for i in range(len(assigns) - 1):
            extras += self._resolve_overwrites_1(assigns[i], assigns[i + 1:])
        return extras

    def _resolve_overwrites_1(self, first, rest):
        extras = []
        target = first.targets[0]
        if any(self._check_conficts(target, o) for o in rest):
            tmp_id = '_{}'.format(self._temp_count)
            self._temp_count += 1
            new_target = ast.Name(tmp_id, ast.Store())
            ttype = target.ttype
            ast.copy_location(new_target, target).ttype = ttype
            first.targets[0] = new_target
            new_value = ast.Name(tmp_id, ast.Load())
            ast.copy_location(new_value, target).ttype = ttype
            new_assign = ast.Assign([target], new_value)
            ast.copy_location(new_assign, first)
            extras.append(new_assign)
        return extras

    class NameChecker(ast.NodeVisitor):
        def __init__(self, name):
            self.id = name.id
            self.n_conflicts = 0

        def visit_Name(self, node):
            if node.id == self.id and isinstance(node.ctx, ast.Load):
                self.n_conflicts += 1

    class AttributeChecker(ast.NodeVisitor):
        def __init__(self, attribute):
            self.id = attribute.value.id
            self.attr = attribute.attr
            self.n_conflicts = 0
    
        def visit_Attribute(self, node):
            if (node.attr == self.attr and
                isinstance(node.ctx, ast.Load) and
                isinstance(node.value, ast.Name) and # conditional and
                node.value.id == self.id):
                self.n_conflicts += 1

    def _check_conficts(self, target, assign):
        if isinstance(target, ast.Name):
            checker = self.NameChecker(target)
        elif isinstance(target, ast.Attribute):
            if not isinstance(target.value, ast.Name):
                raise CompileError("Only supports attributes of names")
            checker = self.AttributeChecker(target)
        else:
            raise CompileError("Unsupported assignment target")
        checker.visit(assign)
        return checker.n_conflicts > 0
